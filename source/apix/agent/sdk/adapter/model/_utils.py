"""Small provider-SDK normalization helpers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from apix.agent.sdk.utils.message import FinishReason


def get_field(value: Any, name: str, default: Any = None) -> Any:
    """Read a field from either an SDK object or a mapping."""
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def model_dump(value: Any) -> dict[str, Any]:
    """Convert SDK metadata to a plain dictionary when possible."""
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)

    dump = getattr(value, "model_dump", None)
    if not callable(dump):
        return {}

    dumped = dump(exclude_none=True)
    return dumped if isinstance(dumped, dict) else {}


def iso_timestamp(created: Any, *, empty: bool = False) -> str:
    """Convert a provider Unix timestamp to an ISO-8601 UTC timestamp."""
    if isinstance(created, (int, float)):
        return datetime.fromtimestamp(created, tz=UTC).isoformat()
    if empty:
        return ""
    return datetime.now(UTC).isoformat()


def normalize_finish_reason(value: Any) -> FinishReason | None:
    """Map provider stop reasons to the APIX message vocabulary."""
    if value is None:
        return None
    if value in {"stop", "length", "tool_calls", "content_filter"}:
        return value
    return "unknown"


def elapsed_milliseconds(started_at: float) -> int:
    """Return non-negative elapsed wall time in milliseconds."""
    return max(0, round((perf_counter() - started_at) * 1000))


def token_usage_info(usage: Any) -> dict[str, int | float]:
    """Flatten token counters from OpenAI and compatible SDK responses.

    Top-level counters keep their provider names (for example,
    ``prompt_tokens`` and ``total_tokens``). Counters nested in details
    objects are promoted when their names are unambiguous. A parent prefix is
    added only when two nested objects expose the same counter name.
    """
    dumped = model_dump(usage)
    token_info: dict[str, int | float] = {}

    def is_counter(name: str, value: Any) -> bool:
        return (
            name.endswith("_tokens")
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        )

    for key, value in dumped.items():
        if is_counter(key, value):
            token_info[key] = value

    for parent, value in dumped.items():
        nested = model_dump(value)
        for key, counter in nested.items():
            if not is_counter(key, counter):
                continue
            target = key if key not in token_info else f"{parent}_{key}"
            token_info[target] = counter

    if "total_tokens" not in token_info:
        if {
            "prompt_tokens",
            "completion_tokens",
        } <= token_info.keys():
            token_info["total_tokens"] = (
                token_info["prompt_tokens"]
                + token_info["completion_tokens"]
            )
        elif {"input_tokens", "output_tokens"} <= token_info.keys():
            token_info["total_tokens"] = (
                token_info["input_tokens"]
                + token_info["output_tokens"]
            )

    return token_info
