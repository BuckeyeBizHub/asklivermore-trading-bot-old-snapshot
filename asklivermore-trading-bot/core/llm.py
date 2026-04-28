"""
core.llm
========
Single Claude client used by all agents. Enforces structured JSON outputs,
applies retries, and pins the model from settings.
"""
from __future__ import annotations

import json
from typing import Any, TypeVar

from anthropic import Anthropic, APIError
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.config import settings
from core.errors import LLMOutputError
from core.logging import get_logger

log = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)

_client: Anthropic | None = None


def client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(APIError),
)
def _call(model: str, system: str, user: str, max_tokens: int = 1500) -> str:
    msg = client().messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=0,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts).strip()


def call_structured(
    *,
    schema: type[T],
    system: str,
    user: str,
    use_reasoning_model: bool = False,
    max_tokens: int = 1500,
) -> T:
    """Call Claude and parse the response into `schema`. Raises LLMOutputError on failure."""
    model = settings.reasoning_model if use_reasoning_model else settings.utility_model
    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    full_system = (
        f"{system}\n\n"
        "You MUST respond with a single JSON object that validates against this schema. "
        "Do not include prose, markdown fences, or commentary outside the JSON.\n\n"
        f"<schema>\n{schema_json}\n</schema>"
    )
    raw = _call(model=model, system=full_system, user=user, max_tokens=max_tokens)
    raw = _strip_fences(raw)
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as e:
        log.error("llm.invalid_json", raw=raw[:500])
        raise LLMOutputError(f"Claude returned invalid JSON: {e}") from e
    try:
        return schema.model_validate(data)
    except ValidationError as e:
        log.error("llm.schema_violation", errors=e.errors(), raw=raw[:500])
        raise LLMOutputError(f"Claude output did not match schema: {e}") from e


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        # tolerate ```json ... ``` even though we asked for none
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s[: -3]
    return s.strip()
