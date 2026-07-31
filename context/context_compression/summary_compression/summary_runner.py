"""Run one injected summary call and return data, never host state."""

from collections.abc import Callable
from typing import Any


def run_summary_generation(
    prompt: str,
    *,
    llm: Callable[[str], Any],
    response_text: Callable[[Any], str],
    think_stripper: Callable[[str], str],
    redactor: Callable[[str], str],
    normalize_summary: Callable[[str], str],
    ground_summary: Callable[[str], str] | None = None,
    validate_summary: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Return an explicit success/failure record for host policy decisions."""
    try:
        response = llm(prompt)
        raw_text = response_text(response)
        if not isinstance(raw_text, str):
            raise TypeError("response_text must return str")
        if not raw_text.strip():
            raise ValueError("summary LLM returned empty content")
        body = think_stripper(raw_text).strip() or raw_text.strip()
        body = redactor(body)
        if ground_summary is not None:
            body = ground_summary(body)
        if validate_summary is not None:
            validate_summary(body)
        summary = normalize_summary(body)
        return {
            "ok": True,
            "summary": summary,
            "body": body,
            "response": response,
            "error": None,
            "error_type": None,
        }
    except Exception as error:
        return {
            "ok": False,
            "summary": None,
            "body": None,
            "response": None,
            "error": str(error) or error.__class__.__name__,
            "error_type": error.__class__.__name__,
        }
