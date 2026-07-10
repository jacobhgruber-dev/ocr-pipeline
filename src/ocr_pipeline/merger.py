"""VLM-based OCR output merging.

Uses a vision-language model (Anthropic Claude or Google Gemini) to merge
outputs from multiple OCR engines into a single authoritative markdown
transcription.  Supports configurable system prompts, engine agreement
computation, and cost estimation.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

from .errors import MergeError
from .models import EngineName, EngineOutput
from .profiles import get_profile

logger = logging.getLogger(__name__)

# ── VLM merge protocol ─────────────────────────────────────────────────────


@runtime_checkable
class VlmMerger(Protocol):
    """Protocol for VLM-based OCR merge/refinement.

    Inject a real implementation (Anthropic or Gemini) in production,
    or a stub in tests.
    """

    def merge(
        self,
        image_path: Path,
        engine_outputs: list[EngineOutput],
        page_index: int,
        pdf_identifier: str,
        system_prompt: str,
        model: str,
        fallback_model: str,
        max_tokens: int,
        timeout_sec: float,
    ) -> tuple[str, str, str, float]:
        """Merge engine outputs into authoritative markdown.

        Returns:
            ``(merged_markdown, raw_api_json, model_used, cost_usd)``.

        Raises:
            MergeError: On failure.
        """
        ...


class DefaultVlmMerger:
    """Production VLM merger using real API calls (Gemini or Claude)."""

    def merge(
        self,
        image_path: Path,
        engine_outputs: list[EngineOutput],
        page_index: int,
        pdf_identifier: str,
        system_prompt: str,
        model: str,
        fallback_model: str,
        max_tokens: int,
        timeout_sec: float,
    ) -> tuple[str, str, str, float]:
        return merge_with_vlm(
            image_path=image_path,
            engine_outputs=engine_outputs,
            page_index=page_index,
            pdf_identifier=pdf_identifier,
            system_prompt=system_prompt,
            model=model,
            fallback_model=fallback_model,
            max_tokens=max_tokens,
            timeout_sec=timeout_sec,
        )


class StubVlmMerger:
    """Test stub that returns canned markdown without making API calls."""

    def __init__(self, canned_text: str = "STUB MERGED TEXT") -> None:
        self.canned_text = canned_text
        self.call_count = 0

    def merge(
        self,
        image_path: Path,
        engine_outputs: list[EngineOutput],
        page_index: int,
        pdf_identifier: str,
        system_prompt: str,
        model: str,
        fallback_model: str,
        max_tokens: int,
        timeout_sec: float,
    ) -> tuple[str, str, str, float]:
        self.call_count += 1
        return self.canned_text, '{"stub": true}', model or "stub", 0.0


def _build_system_prompt(
    profile_name: str = "general",
    column_layout: str = "auto",
    languages: list[str] | None = None,
    custom_prompt: str = "",
) -> str:
    """Assemble the VLM system prompt from profiles.py and layout hints.

    Args:
        profile_name: Name of a :class:`DocumentProfile` (e.g. ``"academic"``,
                      ``"legal"``).  Falls back to ``"general"``.
        column_layout: ``"single"``, ``"dual"``, or ``"auto"``.
        languages: List of ISO 639-1 language codes the document may contain.
        custom_prompt: If non-empty, overrides all template assembly and is
                       returned as-is.

    Returns:
        The assembled system prompt string.
    """
    if custom_prompt:
        return custom_prompt

    profile = get_profile(profile_name)
    base = profile.system_prompt

    # ── Column layout hint ────────────────────────────────────────────
    if column_layout == "dual":
        base += (
            "\n\nLAYOUT: The page uses dual-column layout. Linearize left column first, then right."
        )
    elif column_layout == "single":
        base += "\n\nLAYOUT: The page is single-column. Do not attempt column detection."

    # ── Language hint ─────────────────────────────────────────────────
    if languages and len(languages) > 1:
        lang_list = ", ".join(languages)
        base += (
            f"\n\nLANGUAGES: The document may contain text in: {lang_list}. "
            "Preserve the original language of each passage."
        )

    return base


# ── Provider-specific API callers ─────────────────────────────────────────


def _call_anthropic(
    model: str,
    b64_image: str,
    user_message: str,
    system_prompt: str,
    max_tokens: int,
    timeout_sec: float,
) -> tuple[str, str, float]:
    """Call Anthropic Claude for a single merge attempt (with one retry).

    Returns:
        ``(result_text, raw_json, cost)``.

    Raises:
        MergeError: If both attempts fail.
    """
    import anthropic

    # Check CredentialStore (config.yaml) first, then environment
    api_key = None
    try:
        from .engines.base import CredentialStore

        api_key = CredentialStore().get("ANTHROPIC_API_KEY")
    except Exception:
        pass
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise MergeError(
            "ANTHROPIC_API_KEY is not set. Add it to ocr_pipeline/config.yaml "
            "under credentials.ANTHROPIC_API_KEY, or set the ANTHROPIC_API_KEY "
            "environment variable."
        )

    client = anthropic.Anthropic(api_key=api_key)

    last_error: Exception | None = None
    for attempt in (1, 2):
        try:
            message = client.messages.create(  # type: ignore[attr-defined]
                model=model,
                max_tokens=max_tokens,
                timeout=timeout_sec,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b64_image,
                                },
                            },
                            {
                                "type": "text",
                                "text": user_message,
                            },
                        ],
                    }
                ],
            )
            content_block = message.content[0]  # type: ignore[union-attr]
            if not hasattr(content_block, "text") or not content_block.text:
                raise MergeError("VLM returned no text content")
            result_text: str = content_block.text

            # Capture raw API response for debugging
            usage = getattr(message, "usage", None)
            try:
                raw_json: str = message.model_dump_json()  # type: ignore[union-attr]
            except Exception:
                raw_json = json.dumps(
                    {
                        "model": message.model,  # type: ignore[union-attr]
                        "usage": {
                            "input_tokens": (getattr(usage, "input_tokens", 0) or 0),
                            "output_tokens": (getattr(usage, "output_tokens", 0) or 0),
                        },
                        "stop_reason": getattr(
                            message,
                            "stop_reason",
                            None,  # type: ignore[union-attr]
                        ),
                    }
                )

            # Estimate cost
            cost = 0.0
            if usage is not None:
                input_tokens = getattr(usage, "input_tokens", 0) or 0
                output_tokens = getattr(usage, "output_tokens", 0) or 0
                cost = _estimate_cost_anthropic(input_tokens, output_tokens, model)
            else:
                input_chars = len(user_message) + len(system_prompt)
                output_chars = len(result_text)
                cost = _estimate_cost_anthropic(input_chars, output_chars, model, from_chars=True)

            return result_text, raw_json, cost

        except Exception as exc:
            last_error = exc
            if attempt == 1:
                time.sleep(2.0)
                continue

    raise MergeError(f"Anthropic merge failed after 2 attempts: {last_error}")


def _call_gemini(
    model: str,
    b64_image: str,
    user_message: str,
    system_prompt: str,
    max_tokens: int,
    timeout_sec: float,
) -> tuple[str, str, float]:
    """Call Google Gemini for a single merge attempt (with one retry).

    Returns:
        ``(result_text, raw_json, cost)``.

    Raises:
        MergeError: If both attempts fail.
    """
    from google import genai

    # Check CredentialStore (opencode config) first, then environment
    api_key = None
    try:
        from .engines.base import CredentialStore

        api_key = CredentialStore().get("GEMINI_API_KEY")
    except Exception:
        pass
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise MergeError(
            "GEMINI_API_KEY is not set. Add it to ~/.config/opencode/opencode.json "
            "under credentials.GEMINI_API_KEY, or set the GEMINI_API_KEY "
            "environment variable."
        )

    client = genai.Client(api_key=api_key)

    image_part = genai.types.Part.from_bytes(
        data=base64.b64decode(b64_image),
        mime_type="image/png",
    )

    last_error: Exception | None = None
    for attempt in (1, 2):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[image_part, genai.types.Part.from_text(text=user_message)],  # type: ignore[arg-type]
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=max_tokens,
                ),
            )

            if not response.text:
                raise MergeError("Gemini returned no text content")

            result_text: str = response.text

            # Extract usage metadata
            input_tokens = 0
            output_tokens = 0
            try:
                usage = response.usage_metadata
                if usage is not None:
                    input_tokens = usage.prompt_token_count or 0
                    output_tokens = usage.candidates_token_count or 0
            except Exception:
                pass

            raw_json = json.dumps(
                {
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                }
            )

            cost = _estimate_cost_gemini(input_tokens, output_tokens, model)

            return result_text, raw_json, cost

        except Exception as exc:
            last_error = exc
            if attempt == 1:
                time.sleep(2.0)
                continue

    raise MergeError(f"Gemini merge failed after 2 attempts: {last_error}")


# ── Grok (xAI) ─────────────────────────────────────────────────────────────

_GROK_RATES: dict[str, tuple[float, float]] = {
    "grok-4.5": (2.00, 6.00),
    "grok-4.3": (1.25, 2.50),
    "grok-3": (3.00, 15.00),
}


def _estimate_cost_grok(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    model_lower = model.lower()
    for prefix, (in_r, out_r) in _GROK_RATES.items():
        if prefix in model_lower:
            return (prompt_tokens / 1_000_000) * in_r + (completion_tokens / 1_000_000) * out_r
    return (prompt_tokens / 1_000_000) * 1.25 + (completion_tokens / 1_000_000) * 2.50


def _call_grok(model: str, b64_image: str, user_message: str, system_prompt: str, max_tokens: int, timeout_sec: float) -> tuple[str, str, float]:
    """Call xAI Grok for VLM merge via OpenAI-compatible API."""
    api_key = os.environ.get("XAI_API_KEY", "")
    if not api_key:
        raise MergeError("XAI_API_KEY environment variable is not set")

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")

    messages: list[dict[str, object]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": [
        {"type": "text", "text": user_message},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}", "detail": "high"}},
    ]})

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model, messages=messages, max_tokens=max_tokens, temperature=0.1)  # type: ignore[arg-type]
            content = response.choices[0].message.content or ""
            usage = response.usage
            pt, ct = (usage.prompt_tokens, usage.completion_tokens) if usage else (0, 0)
            cost = _estimate_cost_grok(model, pt, ct)
            return content, json.dumps({"provider": "grok", "model": model, "prompt_tokens": pt, "completion_tokens": ct, "cost_estimated": cost}), cost
        except Exception as exc:
            if attempt == 0:
                time.sleep(2)
            else:
                raise MergeError(f"Grok VLM call failed: {exc}") from exc
    raise MergeError("Grok VLM call failed")


# ── Dispatcher ────────────────────────────────────────────────────────────


def _call_vlm(
    model: str,
    b64_image: str,
    user_message: str,
    system_prompt: str,
    max_tokens: int,
    timeout_sec: float,
) -> tuple[str, str, float]:
    """Dispatch to the appropriate VLM provider based on the model string.

    - Models containing ``"gemini"`` → Google Gemini.
    - Models containing ``"claude"`` or ``"anthropic"`` → Anthropic Claude.
    - Models containing ``"grok"`` → xAI Grok (OpenAI-compatible).

    Returns:
        ``(result_text, raw_json, cost)``.
    """
    model_lower = model.lower()
    if "gemini" in model_lower:
        return _call_gemini(
            model=model, b64_image=b64_image, user_message=user_message,
            system_prompt=system_prompt, max_tokens=max_tokens, timeout_sec=timeout_sec,
        )
    elif any(p in model_lower for p in ("claude", "anthropic")):
        return _call_anthropic(
            model=model, b64_image=b64_image, user_message=user_message,
            system_prompt=system_prompt, max_tokens=max_tokens, timeout_sec=timeout_sec,
        )
    elif "grok" in model_lower:
        return _call_grok(
            model=model, b64_image=b64_image, user_message=user_message,
            system_prompt=system_prompt, max_tokens=max_tokens, timeout_sec=timeout_sec,
        )

    logger.warning(
        "Unknown VLM model '%s' — defaulting to Anthropic API. "
        "Supported: gemini-*, claude-*, grok-*, anthropic-*.",
        model,
    )
    return _call_anthropic(
        model=model, b64_image=b64_image, user_message=user_message,
        system_prompt=system_prompt, max_tokens=max_tokens, timeout_sec=timeout_sec,
    )


# ── Quality check ─────────────────────────────────────────────────────────


def _check_output_quality(result_text: str, marker_text: str) -> bool:
    """Return True if the VLM output looks low-quality and should be retried.

    Checks:
    - ``[illegible]`` appears more than 3 times.
    - Output is more than 80% whitespace or completely empty.
    - Output length is less than 50% of Marker's output length.
    """
    if result_text.count("[illegible]") > 3:
        return True

    stripped = result_text.strip()
    if not stripped:
        return True

    total_len = len(result_text)
    if total_len > 0:
        whitespace_ratio = sum(1 for c in result_text if c.isspace()) / total_len
        if whitespace_ratio > 0.8:
            return True

    marker_stripped = marker_text.strip()
    if marker_stripped and len(stripped) < 0.5 * len(marker_stripped):
        return True

    return False


# ── Public API ────────────────────────────────────────────────────────────


def merge_with_vlm(
    image_path: Path,
    engine_outputs: list[EngineOutput],
    page_index: int,
    pdf_identifier: str,
    system_prompt: str = "",
    model: str = "gemini-2.5-flash",
    fallback_model: str = "claude-sonnet-5",
    max_tokens: int = 4096,
    timeout_sec: float = 120.0,
) -> tuple[str, str, str, float]:
    """Merge multiple OCR outputs into authoritative markdown using a VLM.

    Dispatches to the appropriate provider based on the model string (Gemini
    or Anthropic).  If the primary model produces low-quality output (many
    ``[illegible]`` markers, truncated, or empty) it automatically falls back
    to *fallback_model*.

    Args:
        image_path: Path to the rendered page PNG.
        engine_outputs: List of EngineOutput from different OCR engines.
        page_index: 0-based page number (for logging).
        pdf_identifier: Short identifier for the source PDF.
        system_prompt: VLM system prompt. If empty, uses
                       :data:`DEFAULT_SYSTEM_PROMPT`.
        model: VLM model ID. Default: ``"gemini-2.5-flash"``.
        fallback_model: Model to use if primary model output is low quality.
                        Default: ``"claude-sonnet-5"``.
        max_tokens: Max output tokens.
        timeout_sec: Timeout for the API call.

    Returns:
        ``(merged_markdown, raw_api_json, model_used, cost_estimate)``.
        *cost_estimate* is in USD.

    Raises:
        MergeError: If the merge fails after retries and fallback.
    """
    # Build the user message dynamically from active engines
    active = [eo for eo in engine_outputs if eo.error is None and eo.text.strip()]
    engine_sections: list[str] = []
    for eo in active:
        engine_sections.append(f"--- {eo.engine.upper()} ---\n{eo.text}")

    if not active:
        # If no engines produced usable text, we can still ask the VLM to try from the image alone
        user_message = (
            "The OCR engines failed to extract any text from this page. "
            "Please read the attached image and transcribe the text directly following the system prompt rules."
        )
    else:
        user_message = (
            f"Below are {len(active)} OCR transcription(s) of the same page image.\n"
            "The image is attached for reference. Merge them into the single "
            "most accurate markdown transcription.\n\n" + ("\n\n".join(engine_sections))
        )

    # Keep the old _find_text-style references for backward compatibility
    # in _check_output_quality which needs marker_text specifically.
    marker_text = _find_text(engine_outputs, EngineName.MARKER)

    with open(image_path, "rb") as f:
        b64_image = base64.standard_b64encode(f.read()).decode("utf-8")

    # ── Try primary model ──────────────────────────────────────────────
    result_text, raw_json, cost = _call_vlm(
        model=model,
        b64_image=b64_image,
        user_message=user_message,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        timeout_sec=timeout_sec,
    )
    model_used = model

    # ── Quality gate: fall back if output is sus ───────────────────────
    if _check_output_quality(result_text, marker_text):
        logger.info(
            "%s output low quality for %s page %d — retrying with %s",
            model,
            pdf_identifier,
            page_index,
            fallback_model,
        )
        try:
            fallback_result, fallback_raw, fallback_cost = _call_vlm(
                model=fallback_model,
                b64_image=b64_image,
                user_message=user_message,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                timeout_sec=timeout_sec,
            )
            return fallback_result, fallback_raw, fallback_model, fallback_cost
        except MergeError:
            logger.warning(
                "Fallback %s also failed for %s page %d — using %s result",
                fallback_model,
                pdf_identifier,
                page_index,
                model,
            )

    return result_text, raw_json, model_used, cost


def compute_engine_agreement(outputs: list[EngineOutput]) -> float:
    """Compute a rough similarity score (0.0-1.0) across engine outputs.

    Uses normalized Levenshtein distance on the full text of each output.
    If all pairwise similarities > 0.97, the engines strongly agree and
    VLM merge can be skipped.
    """
    texts = [o.text.strip() for o in outputs if o.error is None]
    if len(texts) < 2:
        return 0.0

    # Length sanity: if outputs differ by >50% in length, they disagree
    lengths = [len(t) for t in texts]
    if max(lengths) > 1.5 * min(lengths) and min(lengths) > 0:
        return 0.0

    scores: list[float] = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            dist = _levenshtein_distance(texts[i], texts[j])
            max_len = max(len(texts[i]), len(texts[j]))
            if max_len == 0:
                scores.append(1.0)
            else:
                scores.append(1.0 - dist / max_len)

    if not scores:
        return 0.0
    return sum(scores) / len(scores)


# ── Cost estimation ──────────────────────────────────────────────────────


# Per-million token rates in USD
_ANTHROPIC_RATES: dict[str, tuple[float, float]] = {
    # Specific model IDs (checked first)
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    # Fallback prefix matches
    "claude-4-opus": (15.0, 75.0),
    "claude-4-sonnet": (3.0, 15.0),
    "claude-3.5-haiku": (1.0, 5.0),
    "claude-3.5-sonnet": (3.0, 15.0),
    "claude-opus": (15.0, 75.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-haiku": (1.0, 5.0),
}

_GEMINI_RATES: dict[str, tuple[float, float]] = {
    # model_prefix: (input_rate_per_M, output_rate_per_M)
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-pro": (3.50, 10.50),
}


def _estimate_cost_anthropic(
    input_tokens: int,
    output_tokens: int,
    model: str,
    from_chars: bool = False,
) -> float:
    """Estimate Anthropic API cost from token counts (or character counts).

    When *from_chars* is True, divides by ~4 to approximate tokens.
    """
    if from_chars:
        chars_per_token = 4.0
        input_tokens = int(input_tokens / chars_per_token)
        output_tokens = int(output_tokens / chars_per_token)

    model_lower = model.lower()
    input_rate = 3.0
    output_rate = 15.0
    for prefix, (in_r, out_r) in _ANTHROPIC_RATES.items():
        if prefix in model_lower:
            input_rate = in_r
            output_rate = out_r
            break

    return (input_tokens / 1_000_000.0) * input_rate + (output_tokens / 1_000_000.0) * output_rate


def _estimate_cost_gemini(
    input_tokens: int,
    output_tokens: int,
    model: str,
) -> float:
    """Estimate Gemini API cost from token counts."""
    model_lower = model.lower()
    input_rate = 0.10
    output_rate = 0.40
    for prefix, (in_r, out_r) in _GEMINI_RATES.items():
        if prefix in model_lower:
            input_rate = in_r
            output_rate = out_r
            break

    return (input_tokens / 1_000_000.0) * input_rate + (output_tokens / 1_000_000.0) * output_rate


# ── Helpers ──────────────────────────────────────────────────────────────


def _find_text(outputs: list[EngineOutput], engine_name: str) -> str:
    """Return the text output for *engine_name*, or a placeholder if not found."""
    for o in outputs:
        if o.engine == engine_name and o.error is None:
            return o.text or "(empty output)"
    return "(not available)"


def _levenshtein_distance(a: str, b: str) -> int:
    """Compute Levenshtein (edit) distance between two strings.

    Pure-Python O(n·m) implementation suitable for short comparison
    windows (~2000 chars each).
    """
    if len(a) < len(b):
        return _levenshtein_distance(b, a)

    # a is the longer string
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            curr.append(prev[j - 1] if ca == cb else 1 + min(prev[j], curr[j - 1], prev[j - 1]))
        prev = curr

    return prev[-1]
