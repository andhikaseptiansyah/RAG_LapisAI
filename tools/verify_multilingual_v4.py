#!/usr/bin/env python3
"""Verify the deployed multilingual V4 backend with the exact P1 query."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

EXPECTED_BUILD = "rag-multilingual-v4-20260723"
DEFAULT_QUESTION = "Seberapa cepat insiden IT P1 harus diselesaikan?"
EXPECTED_SOURCE = "SOP_IT_Incident_Handling.pdf"


def request_json(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = response.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object from {url}.")
    return data


def login(base_url: str, username: str, password: str) -> str:
    response = request_json(
        f"{base_url}/api/auth/login",
        method="POST",
        payload={"username": username, "password": password},
    )
    token = str(response.get("token") or "").strip()
    if not token:
        raise ValueError("Login response did not contain a token.")
    return token


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--model", help="Optional provider/model override. Omit to use backend default.")
    args = parser.parse_args()

    base_url = args.api_url.rstrip("/")
    try:
        health = request_json(f"{base_url}/api/health")
    except Exception as exc:
        print(f"FAIL: backend health request failed: {exc}", file=sys.stderr)
        return 2

    print("Health:")
    print(json.dumps(health, ensure_ascii=False, indent=2))
    active_build = str(health.get("buildVersion") or "")
    if active_build != EXPECTED_BUILD:
        print(
            "\nFAIL: the running backend is not V4.\n"
            f"Expected: {EXPECTED_BUILD}\n"
            f"Actual:   {active_build or '<missing>'}",
            file=sys.stderr,
        )
        return 1

    token = args.token
    if not token and args.username and args.password:
        try:
            token = login(base_url, args.username, args.password)
        except Exception as exc:
            print(f"FAIL: login failed: {exc}", file=sys.stderr)
            return 3

    if not token:
        print(
            "\nPASS: V4 is active. Chat test skipped because no token or credentials were supplied."
        )
        return 0

    try:
        chat_payload: dict[str, object] = {
            "message": args.question,
            "language": "ID",
        }
        if args.model:
            chat_payload["model"] = args.model
        response = request_json(
            f"{base_url}/api/chat",
            method="POST",
            token=token,
            payload=chat_payload,
        )
    except Exception as exc:
        print(f"FAIL: chat request failed: {exc}", file=sys.stderr)
        return 4

    print("\nChat response:")
    print(json.dumps(response, ensure_ascii=False, indent=2))

    answer = str(response.get("answer") or "").casefold()
    sources = response.get("sources") or []
    source_names = {
        str(item.get("document_name") or item.get("documentName") or "")
        for item in sources
        if isinstance(item, dict)
    }

    if "4 jam" not in answer:
        print("\nFAIL: the answer does not contain '4 jam'.", file=sys.stderr)
        return 5
    if EXPECTED_SOURCE not in source_names:
        print(f"\nFAIL: expected source {EXPECTED_SOURCE} was not returned.", file=sys.stderr)
        return 6

    print(
        "\nPASS: Indonesian P1 query returned 4 jam with the expected source.\n"
        f"retrieval_mode={response.get('retrieval_mode')}\n"
        f"retrieval_query={response.get('retrieval_query')}\n"
        f"generation_mode={response.get('generation_mode')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
