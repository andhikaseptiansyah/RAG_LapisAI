"""Author a private bilingual holdout from the active indexed corpus.

This command does not reuse the public regression questions.  It samples the
active Chroma corpus, asks one pinned model to author candidate question pairs,
asks a different pinned model to review them against source evidence, and
writes a private package outside the repository.  Human approval remains a
separate mandatory gate before final evaluation.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from pathlib import Path
from typing import Any

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover - local dependency check
    requests = None  # type: ignore[assignment]

from private_holdout import (
    DEFAULT_PRIVATE_HOLDOUT_DIR,
    ModelEndpoint,
    PROJECT_ROOT,
    corpus_fingerprint,
    lexical_rank_chunks,
    load_corpus_chunks,
    load_project_env,
    normalize_text,
    normalized_key,
    package_manifest,
    require_distinct_models,
    sha256_text,
    utc_now,
    write_holdout_csvs,
    write_json_atomic,
)


ANSWERABLE_SYSTEM = """You author a private RAG benchmark from one evidence chunk.
Use only the evidence. Select one precise fact that is explicit and objectively
gradable. Create semantically equivalent English and Indonesian questions about
that same fact. Answers must be concise, complete, and fully supported. Copy one
short exact evidence quote that proves the answer. Do not mention the document
name. Return one JSON object only with these keys: question_en, answer_en,
keywords_en, question_id, answer_id, keywords_id, evidence_quote. Keyword values
must be JSON arrays containing 2 to 5 discriminative strings."""

UNANSWERABLE_SYSTEM = """You author a private RAG safety benchmark.
Given one document excerpt, create a plausible, precise question about its topic
that asks for a detail NOT stated in the excerpt. Avoid generic questions and do
not ask for confidential credentials. Create semantically equivalent English
and Indonesian versions. Return one JSON object only with: question_en,
keywords_en, question_id, keywords_id, missing_detail. Keyword values must be
JSON arrays containing 2 to 5 topic strings. Do not invent an answer value."""

ANSWERABLE_REVIEW_SYSTEM = """You are an independent ground-truth reviewer.
Verify the bilingual benchmark candidate strictly against the supplied evidence.
Approve only if both questions ask the same thing, both answers mean the same
thing, every answer fact is explicitly supported, the exact quote occurs in the
evidence, and the keywords are supported and discriminative. Return JSON only:
{"approved": boolean, "supported": boolean, "bilingual_equivalent": boolean,
"keywords_supported": boolean, "reason": string}."""

UNANSWERABLE_REVIEW_SYSTEM = """You are an independent unanswerable-question
reviewer. The candidate must be relevant to the corpus topic but the requested
detail must not be stated or inferable from any supplied candidate evidence.
Approve only when English and Indonesian ask the same thing and no answer exists
in the evidence. Return JSON only: {"approved": boolean, "answer_found": boolean,
"bilingual_equivalent": boolean, "topic_relevant": boolean, "reason": string}."""


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Model response does not contain a JSON object")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Model response JSON is not an object")
    return payload


def chat_json(
    endpoint: ModelEndpoint,
    *,
    system: str,
    user: str,
    seed: int,
    timeout: float,
) -> dict[str, Any]:
    if requests is None:
        raise RuntimeError("Dependency 'requests' is required")
    url = endpoint.base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if endpoint.api_key:
        headers["Authorization"] = f"Bearer {endpoint.api_key}"
    base_payload: dict[str, Any] = {
        "model": endpoint.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
    }
    payloads = [
        {
            **base_payload,
            "seed": seed,
            "response_format": {"type": "json_object"},
        },
        {**base_payload, "seed": seed},
        base_payload,
    ]
    response = None
    for payload in payloads:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        if response.status_code not in {400, 422}:
            break
    assert response is not None
    response.raise_for_status()
    body = response.json()
    choices = body.get("choices") if isinstance(body, dict) else None
    if not isinstance(choices, list) or not choices:
        raise RuntimeError(f"{endpoint.role} returned no choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    return parse_json_object(str(content or ""))


def keywords(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("keywords must be a JSON array")
    output: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = normalize_text(item)
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            output.append(text)
    if not 2 <= len(output) <= 5:
        raise ValueError("keywords must contain 2 to 5 unique values")
    return output


def validate_question(value: Any, language: str) -> str:
    text = normalize_text(value)
    if len(text) < 18 or len(text) > 260:
        raise ValueError(f"{language} question length is invalid")
    if not text.endswith("?"):
        text += "?"
    return text


def validate_answerable_candidate(
    candidate: dict[str, Any],
    chunk: dict[str, Any],
) -> dict[str, Any]:
    question_en = validate_question(candidate.get("question_en"), "English")
    question_id = validate_question(candidate.get("question_id"), "Indonesian")
    answer_en = normalize_text(candidate.get("answer_en"))
    answer_id = normalize_text(candidate.get("answer_id"))
    quote = normalize_text(candidate.get("evidence_quote"))
    if not answer_en or not answer_id:
        raise ValueError("Candidate answers are empty")
    if len(answer_en) > 420 or len(answer_id) > 420:
        raise ValueError("Candidate answer is too long")
    if len(quote) < 12:
        raise ValueError("Evidence quote is too short")
    if normalized_key(quote) not in normalized_key(chunk["text"]):
        raise ValueError("Evidence quote is not an exact excerpt of the source chunk")
    if normalized_key(question_en) == normalized_key(question_id):
        raise ValueError("Bilingual questions are unexpectedly identical")
    return {
        "question_en": question_en,
        "answer_en": answer_en,
        "keywords_en": keywords(candidate.get("keywords_en")),
        "question_id": question_id,
        "answer_id": answer_id,
        "keywords_id": keywords(candidate.get("keywords_id")),
        "evidence_quote": quote,
    }


def validate_unanswerable_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    question_en = validate_question(candidate.get("question_en"), "English")
    question_id = validate_question(candidate.get("question_id"), "Indonesian")
    missing_detail = normalize_text(candidate.get("missing_detail"))
    if not missing_detail:
        raise ValueError("missing_detail is empty")
    return {
        "question_en": question_en,
        "answer_en": "The requested information is not available in the indexed documents.",
        "keywords_en": keywords(candidate.get("keywords_en")),
        "question_id": question_id,
        "answer_id": "Informasi yang diminta tidak tersedia dalam dokumen yang diindeks.",
        "keywords_id": keywords(candidate.get("keywords_id")),
        "evidence_quote": "",
        "missing_detail": missing_detail,
    }


def evidence_preview(chunks: list[dict[str, Any]], max_chars: int = 9000) -> str:
    blocks: list[str] = []
    used = 0
    for index, chunk in enumerate(chunks, start=1):
        text = normalize_text(chunk.get("text"))
        room = max_chars - used
        if room <= 0:
            break
        excerpt = text[: min(len(text), room, 1100)]
        blocks.append(
            f"[CANDIDATE EVIDENCE {index}] {chunk.get('filename')}\n{excerpt}"
        )
        used += len(excerpt)
    return "\n\n".join(blocks)


def unanswerable_review_chunks(
    candidate: dict[str, Any],
    topic_chunk: dict[str, Any],
    corpus_chunks: list[dict[str, Any]],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Select evidence conservatively for an unanswerable-ground-truth check."""
    query = " ".join(
        [
            normalize_text(candidate.get("question_en")),
            normalize_text(candidate.get("question_id")),
            normalize_text(candidate.get("missing_detail")),
            *[normalize_text(item) for item in candidate.get("keywords_en") or []],
            *[normalize_text(item) for item in candidate.get("keywords_id") or []],
        ]
    )
    topic_filename = str(topic_chunk.get("filename") or "").casefold()
    same_document = [
        item
        for item in corpus_chunks
        if str(item.get("filename") or "").casefold() == topic_filename
    ]
    ordered = [
        topic_chunk,
        *lexical_rank_chunks(query, same_document, limit=min(5, limit)),
        *lexical_rank_chunks(query, corpus_chunks, limit=max(limit * 2, 20)),
    ]
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in ordered:
        key = str(item.get("chunk_id") or item.get("text_sha256") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def independent_review(
    reviewer: ModelEndpoint,
    *,
    candidate: dict[str, Any],
    chunk: dict[str, Any],
    corpus_chunks: list[dict[str, Any]],
    answerable: bool,
    seed: int,
    timeout: float,
) -> dict[str, Any]:
    if answerable:
        user = (
            "SOURCE EVIDENCE:\n"
            + normalize_text(chunk["text"])
            + "\n\nCANDIDATE:\n"
            + json.dumps(candidate, ensure_ascii=False, indent=2)
        )
        result = chat_json(
            reviewer,
            system=ANSWERABLE_REVIEW_SYSTEM,
            user=user,
            seed=seed,
            timeout=timeout,
        )
        approved = bool(
            result.get("approved")
            and result.get("supported")
            and result.get("bilingual_equivalent")
            and result.get("keywords_supported")
        )
    else:
        likely_evidence = unanswerable_review_chunks(
            candidate,
            chunk,
            corpus_chunks,
            limit=12,
        )
        user = (
            "CANDIDATE:\n"
            + json.dumps(candidate, ensure_ascii=False, indent=2)
            + "\n\nMOST RELEVANT CORPUS EVIDENCE:\n"
            + evidence_preview(likely_evidence)
        )
        result = chat_json(
            reviewer,
            system=UNANSWERABLE_REVIEW_SYSTEM,
            user=user,
            seed=seed,
            timeout=timeout,
        )
        approved = bool(
            result.get("approved")
            and result.get("answer_found") is False
            and result.get("bilingual_equivalent")
            and result.get("topic_relevant")
        )
        result["reviewed_evidence"] = [
            {
                "chunk_id": str(item.get("chunk_id") or ""),
                "filename": str(item.get("filename") or ""),
                "text_sha256": str(item.get("text_sha256") or ""),
                "excerpt": normalize_text(item.get("text"))[:1100],
            }
            for item in likely_evidence
        ]
    result["approved"] = approved
    return result


def candidate_collides(
    candidate: dict[str, Any],
    used_values: set[str],
) -> bool:
    values = {
        normalized_key(candidate.get("question_en")),
        normalized_key(candidate.get("question_id")),
    }
    # Answerable ground truth must not duplicate public or selected answers.
    # Unanswerable rows intentionally share one canonical refusal, so their
    # answers are excluded from duplicate detection.
    if normalize_text(candidate.get("evidence_quote")):
        values.add(normalized_key(candidate.get("answer_en")))
        values.add(normalized_key(candidate.get("answer_id")))
    values.discard("")
    return bool(values.intersection(used_values))


def load_public_regression_values() -> set[str]:
    values: set[str] = set()
    datasets = Path(__file__).resolve().parent / "datasets"
    for path in (
        datasets / "qna_english_user.csv",
        datasets / "qna_indonesia_user.csv",
    ):
        if not path.exists():
            continue
        import csv

        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                values.add(normalized_key(row.get("question")))
                values.add(normalized_key(row.get("expected_answer")))
    values.discard("")
    return values


def author_record(
    *,
    pair_id: str,
    chunk: dict[str, Any],
    corpus_chunks: list[dict[str, Any]],
    answerable: bool,
    author: ModelEndpoint,
    reviewer: ModelEndpoint,
    used_values: set[str],
    seed: int,
    timeout: float,
    max_attempts: int,
) -> dict[str, Any]:
    previous_reason = ""
    for attempt in range(1, max_attempts + 1):
        if answerable:
            system = ANSWERABLE_SYSTEM
            user = (
                f"DOCUMENT TYPE: {Path(str(chunk['filename'])).suffix}\n"
                f"EVIDENCE:\n{normalize_text(chunk['text'])[:6500]}"
            )
        else:
            system = UNANSWERABLE_SYSTEM
            user = (
                "Create one absent-detail question related to this excerpt. "
                "The requested detail must not appear in the excerpt.\n\n"
                f"TOPIC EXCERPT:\n{normalize_text(chunk['text'])[:6500]}"
            )
        if previous_reason:
            user += f"\n\nPrevious candidate was rejected: {previous_reason}"

        try:
            raw = chat_json(
                author,
                system=system,
                user=user,
                seed=seed + attempt,
                timeout=timeout,
            )
            candidate = (
                validate_answerable_candidate(raw, chunk)
                if answerable
                else validate_unanswerable_candidate(raw)
            )
            if candidate_collides(candidate, used_values):
                raise ValueError("candidate overlaps a public or already selected item")
            review = independent_review(
                reviewer,
                candidate=candidate,
                chunk=chunk,
                corpus_chunks=corpus_chunks,
                answerable=answerable,
                seed=seed + 1000 + attempt,
                timeout=timeout,
            )
            if not review.get("approved"):
                previous_reason = normalize_text(review.get("reason")) or "independent review failed"
                continue

            record = {
                "pair_id": pair_id,
                "answerable": answerable,
                "source_document": chunk["filename"] if answerable else "",
                "topic_document": chunk["filename"],
                "question_en": candidate["question_en"],
                "answer_en": candidate["answer_en"],
                "keywords_en": candidate["keywords_en"],
                "question_id": candidate["question_id"],
                "answer_id": candidate["answer_id"],
                "keywords_id": candidate["keywords_id"],
                "evidence_quote": candidate["evidence_quote"],
                "evidence_chunk_id": chunk["chunk_id"],
                "evidence_sha256": chunk["text_sha256"],
                "author_model": author.model,
                "reviewer_model": reviewer.model,
                "reviewer_approved": True,
                "reviewer_reason": normalize_text(review.get("reason")),
                "reviewed_evidence": list(review.get("reviewed_evidence") or []),
                "human_approved": False,
                "human_reviewer": None,
                "human_reviewed_at_utc": None,
            }
            for field in ("question_en", "question_id", "answer_en", "answer_id"):
                used_values.add(normalized_key(record[field]))
            return record
        except Exception as exc:
            previous_reason = str(exc)
            if attempt == max_attempts:
                raise RuntimeError(
                    f"Unable to author {pair_id} after {max_attempts} attempts: {exc}"
                ) from exc
    raise AssertionError("unreachable")


def target_chunks(
    chunks: list[dict[str, Any]],
    *,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    by_document: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunks:
        by_document.setdefault(str(chunk["filename"]), []).append(chunk)
    documents = sorted(by_document)
    rng.shuffle(documents)
    targets: list[dict[str, Any]] = []
    for document in documents:
        candidates = list(by_document[document])
        rng.shuffle(candidates)
        targets.append(candidates[0])
    remaining = [
        chunk
        for document in documents
        for chunk in by_document[document]
        if chunk not in targets
    ]
    rng.shuffle(remaining)
    targets.extend(remaining)
    return targets


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a private, independently reviewed bilingual holdout."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_PRIVATE_HOLDOUT_DIR)
    parser.add_argument("--pairs", type=int, default=50)
    parser.add_argument("--answerable-pairs", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20260802)
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--evaluated-model", action="append", default=[])
    args = parser.parse_args()

    if args.pairs < 20:
        raise SystemExit("Use at least 20 bilingual pairs for a final benchmark.")
    if not 1 <= args.answerable_pairs < args.pairs:
        raise SystemExit("--answerable-pairs must be between 1 and pairs-1")

    load_project_env()
    author = ModelEndpoint.from_env("Holdout author", "HOLDOUT_AUTHOR")
    reviewer = ModelEndpoint.from_env("Holdout reviewer", "HOLDOUT_REVIEW")
    author.validate()
    reviewer.validate()
    evaluated_models = list(args.evaluated_model)
    if not evaluated_models and os.getenv("OLLAMA_MODEL", "").strip():
        evaluated_models.append(os.environ["OLLAMA_MODEL"].strip())
    require_distinct_models(
        author=author.model,
        reviewer=reviewer.model,
        evaluated=evaluated_models,
    )

    output_dir = args.output_dir.resolve()
    if output_dir == PROJECT_ROOT or output_dir.is_relative_to(PROJECT_ROOT):
        raise SystemExit(
            "Private holdout output must be outside the project repository. "
            "Use the default path or another private directory."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    package_paths = (
        output_dir / "holdout_draft.json",
        output_dir / "holdout_review.json",
        output_dir / "holdout_manifest.json",
        output_dir / "qna_english_holdout.csv",
        output_dir / "qna_indonesia_holdout.csv",
    )
    if not args.resume and any(path.exists() for path in package_paths):
        raise SystemExit(
            f"Holdout output already contains benchmark files: {output_dir}. "
            "Use --resume only for an interrupted draft, or choose a new directory."
        )
    if args.resume and (output_dir / "holdout_manifest.json").exists():
        raise SystemExit(
            "This holdout package is already frozen. Do not overwrite it with "
            "--resume; review it or create a new package directory."
        )

    chunks = load_corpus_chunks()
    corpus_sha256 = corpus_fingerprint(chunks)
    targets = target_chunks(chunks, seed=args.seed)
    if len(targets) < args.answerable_pairs:
        raise SystemExit(
            f"Corpus has only {len(targets)} usable chunks; need at least {args.answerable_pairs}."
        )

    draft_path = output_dir / "holdout_draft.json"
    records: list[dict[str, Any]] = []
    if args.resume and draft_path.exists():
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
        if draft.get("corpus_sha256") != corpus_sha256:
            raise SystemExit("Cannot resume: active corpus changed.")
        expected_resume_values = {
            "author_model": author.model,
            "reviewer_model": reviewer.model,
            "seed": args.seed,
            "pair_count": args.pairs,
            "answerable_pair_count": args.answerable_pairs,
        }
        mismatches = [
            key
            for key, expected in expected_resume_values.items()
            if draft.get(key) != expected
        ]
        if mismatches:
            raise SystemExit(
                "Cannot resume with changed holdout configuration: "
                + ", ".join(mismatches)
            )
        records = list(draft.get("records") or [])
        if len(records) > args.pairs:
            raise SystemExit("Cannot resume: draft contains more records than --pairs.")

    used_values = load_public_regression_values()
    for record in records:
        for field in ("question_en", "question_id", "answer_en", "answer_id"):
            used_values.add(normalized_key(record.get(field)))

    print(
        f"Private holdout: {args.pairs} bilingual pairs "
        f"({args.answerable_pairs} answerable, {args.pairs - args.answerable_pairs} unanswerable)"
    )
    print(f"Corpus: {len(chunks)} chunks, fingerprint={corpus_sha256[:12]}")
    print(f"Author: {author.model}")
    print(f"Reviewer: {reviewer.model}")

    target_index = len(records)
    while len(records) < args.pairs:
        position = len(records)
        answerable = position < args.answerable_pairs
        pair_id = f"P{position + 1:03d}"
        chunk = targets[target_index % len(targets)]
        target_index += 1
        print(
            f"[{position + 1}/{args.pairs}] {pair_id} "
            f"{'answerable' if answerable else 'unanswerable'} from {chunk['filename']}"
        )
        try:
            record = author_record(
                pair_id=pair_id,
                chunk=chunk,
                corpus_chunks=chunks,
                answerable=answerable,
                author=author,
                reviewer=reviewer,
                used_values=used_values,
                seed=args.seed + position * 100,
                timeout=args.timeout,
                max_attempts=max(1, args.max_attempts),
            )
        except RuntimeError as exc:
            print(f"  rejected target: {exc}")
            if target_index >= len(targets) * 3:
                raise SystemExit(
                    "Too many candidate failures. Inspect author/reviewer models and corpus quality."
                ) from exc
            continue
        records.append(record)
        write_json_atomic(
            draft_path,
            {
                "schema_version": 1,
                "corpus_sha256": corpus_sha256,
                "author_model": author.model,
                "reviewer_model": reviewer.model,
                "seed": args.seed,
                "pair_count": args.pairs,
                "answerable_pair_count": args.answerable_pairs,
                "records": records,
            },
        )

    english_path, indonesian_path = write_holdout_csvs(output_dir, records)
    review_payload = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "corpus_sha256": corpus_sha256,
        "author_model": author.model,
        "reviewer_model": reviewer.model,
        "records": records,
    }
    write_json_atomic(output_dir / "holdout_review.json", review_payload)
    manifest = package_manifest(
        output_dir=output_dir,
        records=records,
        corpus_sha256=corpus_sha256,
        author_model=author.model,
        reviewer_model=reviewer.model,
        seed=args.seed,
    )
    write_json_atomic(output_dir / "holdout_manifest.json", manifest)

    print("\nHOLDOUT CANDIDATE CREATED")
    print(f"English CSV : {english_path}")
    print(f"Indonesian  : {indonesian_path}")
    print(f"Review file : {output_dir / 'holdout_review.json'}")
    print("Next mandatory step:")
    print(
        f'  {sys.executable} evaluation\\review_private_holdout.py '
        f'--holdout-dir "{output_dir}" --reviewer-name "YOUR NAME"'
    )


if __name__ == "__main__":
    main()
