#!/usr/bin/env python3
"""Verify that the multilingual V3 backend is the process actually serving requests.

This script uses only the Python standard library. It checks the public health
endpoint first. When an administrator bearer token is supplied, it also runs the
retrieval diagnostic for the exact Indonesian P1 incident question.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

EXPECTED_BUILD = "rag-multilingual-v3-20260723"
DEFAULT_QUESTION = "Seberapa cepat insiden IT P1 harus diselesaikan?"


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

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object from {url}.")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="Backend base URL without /api, default: http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--token",
        help="Optional administrator bearer token for retrieval diagnostics.",
    )
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    args = parser.parse_args()

    base_url = args.api_url.rstrip("/")
    try:
        health = request_json(f"{base_url}/api/health")
    except (urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: health endpoint cannot be verified: {exc}", file=sys.stderr)
        return 2

    active_build = str(health.get("buildVersion") or "")
    print(json.dumps(health, ensure_ascii=False, indent=2))
    if active_build != EXPECTED_BUILD:
        print(
            "\nFAIL: the running server is not multilingual V3.\n"
            f"Expected: {EXPECTED_BUILD}\n"
            f"Actual:   {active_build or '<missing>'}\n"
            "Restart or redeploy the backend that VITE_API_URL points to.",
            file=sys.stderr,
        )
        return 1

    print(f"\nPASS: active backend build is {EXPECTED_BUILD}.")
    if not args.token:
        print("Retrieval debug skipped because --token was not supplied.")
        return 0

    try:
        debug = request_json(
            f"{base_url}/api/admin/retrieval-debug",
            method="POST",
            token=args.token,
            payload={"question": args.question, "topK": 5},
        )
    except (urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: retrieval diagnostic failed: {exc}", file=sys.stderr)
        return 3

    print("\nRetrieval diagnostic:")
    print(json.dumps(debug, ensure_ascii=False, indent=2))
    final_candidates = debug.get("finalCandidates") or []
    if not isinstance(final_candidates, list) or not final_candidates:
        print(
            "\nFAIL: V3 is active, but retrieval returned no accepted candidate. "
            "Inspect the diagnostic scores, indexed collection, and document metadata.",
            file=sys.stderr,
        )
        return 4

    print("\nPASS: the strict retrieval pipeline returned at least one candidate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
