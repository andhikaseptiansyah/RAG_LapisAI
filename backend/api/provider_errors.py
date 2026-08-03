"""Structured errors for upstream LLM providers.

Provider SDKs expose rate limits in different shapes.  Normalising them here
prevents the evaluation endpoint from turning a useful upstream 429 into an
opaque HTTP 500.
"""

from __future__ import annotations

import re
from typing import Any, Mapping


_STATUS_NAMES = (
    "RESOURCE_EXHAUSTED",
    "UNAUTHENTICATED",
    "PERMISSION_DENIED",
    "INVALID_ARGUMENT",
    "UNAVAILABLE",
    "DEADLINE_EXCEEDED",
    "INTERNAL",
)


def _integer_status(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        status = int(value)
    except (TypeError, ValueError):
        match = re.search(r"\b([1-5][0-9]{2})\b", str(value or ""))
        status = int(match.group(1)) if match else 0
    return status if 100 <= status <= 599 else None


def _header(headers: Any, name: str) -> str:
    if not isinstance(headers, Mapping):
        return ""
    wanted = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == wanted:
            return str(value or "").strip()
    return ""


def _duration_seconds(value: Any) -> float | None:
    text = str(value or "").strip().casefold()
    if not text:
        return None
    try:
        return max(0.0, float(text))
    except ValueError:
        pass

    match = re.fullmatch(
        r"(?:(?P<minutes>[0-9]+(?:\.[0-9]+)?)m)?"
        r"(?:(?P<seconds>[0-9]+(?:\.[0-9]+)?)s)?",
        text,
    )
    if not match or not any(match.groupdict().values()):
        return None
    minutes = float(match.group("minutes") or 0.0)
    seconds = float(match.group("seconds") or 0.0)
    return max(0.0, minutes * 60.0 + seconds)


def _retry_after_seconds(raw: str, headers: Any = None) -> float | None:
    header_value = _header(headers, "retry-after")
    parsed_header = _duration_seconds(header_value)
    if parsed_header is not None:
        return parsed_header

    patterns = (
        r"retryDelay['\"\s:]+['\"]?([0-9]+(?:\.[0-9]+)?s)",
        r"retry(?:\s+in|\s+after)?\s+([0-9]+(?:\.[0-9]+)?s)",
    )
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.I)
        if match:
            parsed = _duration_seconds(match.group(1))
            if parsed is not None:
                return parsed
    return None


def _quota_scope(raw: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", "", raw.casefold())
    if any(
        marker in compact
        for marker in (
            "requestsperday",
            "generatedrequestsperday",
            "perprojectpermodelday",
            "dailyquota",
            "ratelimitday",
        )
    ) or re.search(r"\b(per day|daily|rpd)\b", raw, flags=re.I):
        return "daily"
    if any(
        marker in compact
        for marker in (
            "requestsperminute",
            "tokensperminute",
            "perprojectpermodelminute",
            "minutequota",
        )
    ) or re.search(r"\b(per minute|rpm|tpm)\b", raw, flags=re.I):
        return "minute"
    return "unknown"


def _error_code(raw: str) -> str:
    upper = raw.upper()
    for name in _STATUS_NAMES:
        if name in upper:
            return name
    return ""


class ProviderAPIError(RuntimeError):
    """Safe, structured representation of one upstream provider failure."""

    def __init__(
        self,
        provider: str,
        message: str,
        *,
        upstream_status: int | None = None,
        error_code: str = "",
        retry_after_seconds: float | None = None,
        quota_scope: str = "unknown",
    ) -> None:
        super().__init__(message)
        self.provider = str(provider or "provider").strip().casefold()
        self.upstream_status = upstream_status
        self.error_code = str(error_code or "").strip().upper()
        self.retry_after_seconds = retry_after_seconds
        self.quota_scope = quota_scope if quota_scope in {"daily", "minute"} else "unknown"

    @property
    def retryable(self) -> bool:
        status = self.upstream_status
        return status is None or status in {408, 429} or status >= 500

    @property
    def http_status(self) -> int:
        if self.upstream_status == 429:
            return 429
        if self.upstream_status is None or self.upstream_status in {408} or (
            self.upstream_status is not None and self.upstream_status >= 500
        ):
            return 503
        return 502

    def as_detail(self) -> dict[str, Any]:
        return {
            "error": "provider_api_error",
            "provider": self.provider,
            "message": str(self),
            "upstream_status": self.upstream_status,
            "code": self.error_code,
            "retryable": self.retryable,
            "quota_scope": self.quota_scope,
            "retry_after_seconds": self.retry_after_seconds,
        }

    @classmethod
    def from_exception(cls, provider: str, error: Exception) -> "ProviderAPIError":
        raw = str(error or "")
        status = _integer_status(getattr(error, "status_code", None))
        if status is None:
            status = _integer_status(getattr(error, "code", None))
        response = getattr(error, "response", None)
        if status is None and response is not None:
            status = _integer_status(getattr(response, "status_code", None))
        if status is None:
            status = _integer_status(raw)
        if status is None and "RESOURCE_EXHAUSTED" in raw.upper():
            status = 429

        headers = getattr(response, "headers", None) if response is not None else None
        return cls(
            provider,
            _safe_provider_message(provider, status, _quota_scope(raw)),
            upstream_status=status,
            error_code=_error_code(raw),
            retry_after_seconds=_retry_after_seconds(raw, headers),
            quota_scope=_quota_scope(raw),
        )

    @classmethod
    def from_http_response(cls, provider: str, response: Any) -> "ProviderAPIError":
        status = _integer_status(getattr(response, "status_code", None))
        body = str(getattr(response, "text", "") or "")
        scope = _quota_scope(body)
        return cls(
            provider,
            _safe_provider_message(provider, status, scope),
            upstream_status=status,
            error_code=_error_code(body),
            retry_after_seconds=_retry_after_seconds(
                body,
                getattr(response, "headers", None),
            ),
            quota_scope=scope,
        )


def _safe_provider_message(
    provider: str,
    status: int | None,
    quota_scope: str,
) -> str:
    label = str(provider or "provider").strip().title()
    if status == 429 and quota_scope == "daily":
        return (
            f"{label} daily API quota is exhausted. Wait for the quota reset "
            "or increase the API project's quota, then resume the evaluation."
        )
    if status == 429:
        return f"{label} API rate limit reached. Retry the evaluation later."
    if status in {401, 403}:
        return f"{label} rejected the configured API credentials or project access."
    if status in {408} or (status is not None and status >= 500):
        return f"{label} API is temporarily unavailable."
    return f"{label} API request failed."
