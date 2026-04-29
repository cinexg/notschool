"""Shared Gemini call helper with model fallback on quota / transient errors.

The free tier has aggressive per-minute and per-day quotas. When the primary
model returns 429 RESOURCE_EXHAUSTED, we transparently fall back to lighter /
older models so the user still gets a response instead of a hard error.
"""
import os
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception


# Ordered from most capable -> lighter. Each has its own free-tier quota bucket,
# so falling back to the next model usually works even when the first is rate-limited.
# 1.5 family was deprecated in 2025 and now 404s — do not put them in the chain.
DEFAULT_MODEL_CHAIN = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
)


class GeminiUnavailableError(RuntimeError):
    """Raised when every model in the fallback chain has failed."""


def is_transient(exc: Exception) -> bool:
    msg = str(exc)
    return "503" in msg or "UNAVAILABLE" in msg or "429" in msg or "RESOURCE_EXHAUSTED" in msg


def _is_quota(exc: Exception) -> bool:
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiUnavailableError("GEMINI_API_KEY is not configured on the server.")
    return genai.Client(api_key=api_key)


def generate_with_fallback(
    contents,
    *,
    config: types.GenerateContentConfig | None = None,
    models: tuple[str, ...] = DEFAULT_MODEL_CHAIN,
    attempts_per_model: int = 2,
) -> str:
    """Call Gemini, walking the model chain on quota errors.

    Within a single model we still retry transient 503/UNAVAILABLE with backoff,
    but on 429 we move on to the next model immediately rather than waiting out
    the (often 50+ second) cool-down.
    """
    client = get_client()
    last_exc: Exception | None = None

    for model in models:
        @retry(
            retry=retry_if_exception(lambda e: is_transient(e) and not _is_quota(e)),
            stop=stop_after_attempt(attempts_per_model),
            wait=wait_exponential(multiplier=1, min=2, max=8),
            reraise=True,
        )
        def _call():
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            return response.text or ""

        try:
            return _call()
        except Exception as e:
            last_exc = e
            if _is_quota(e) or is_transient(e):
                # Quota OR transient (503/UNAVAILABLE) — try the next model.
                continue
            # Genuine non-recoverable error — surface immediately.
            raise

    raise GeminiUnavailableError(
        f"All Gemini models are unavailable right now. Last error: {last_exc}"
    )
