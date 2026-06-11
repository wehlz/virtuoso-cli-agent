"""Gemini model names and migration helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_GEMINI_FLASH = "gemini-2.5-flash"
DEFAULT_GEMINI_PRO = "gemini-2.5-pro"

# Google shut down 2.0 Flash on the free tier (quota limit: 0). Map old names to current ones.
DEPRECATED_MODEL_ALIASES = {
    "gemini-2.0-flash": DEFAULT_GEMINI_FLASH,
    "gemini-2.0-flash-lite": "gemini-2.5-flash-lite",
    "gemini-1.5-flash": DEFAULT_GEMINI_FLASH,
    "gemini-1.5-flash-latest": DEFAULT_GEMINI_FLASH,
    "gemini-1.5-flash-8b": DEFAULT_GEMINI_FLASH,
    "gemini-1.5-pro": DEFAULT_GEMINI_PRO,
    "gemini-1.5-pro-latest": DEFAULT_GEMINI_PRO,
}

# When the configured model hits quota 0 / 429, try these in order.
QUOTA_FALLBACK_CHAIN: List[str] = [
    DEFAULT_GEMINI_FLASH,
    "gemini-2.5-flash-lite",
    DEFAULT_GEMINI_PRO,
]


def normalize_gemini_model(model: Optional[str]) -> str:
    if not model:
        return DEFAULT_GEMINI_FLASH
    return DEPRECATED_MODEL_ALIASES.get(model.strip(), model.strip())


def resolve_gemini_model_from_config(gem_cfg: Dict[str, Any], backend: str = "") -> str:
    model = gem_cfg.get("model")
    if not model:
        if backend == "gemini-pro" or gem_cfg.get("model") == DEFAULT_GEMINI_PRO:
            model = gem_cfg.get("model_pro", DEFAULT_GEMINI_PRO)
        else:
            model = gem_cfg.get("model_flash", DEFAULT_GEMINI_FLASH)
    return normalize_gemini_model(model)


def apply_gemini_model_defaults(config: Dict[str, Any]) -> None:
    """Rewrite deprecated Gemini model names in an in-memory config dict."""
    llm = config.setdefault("llm", {})
    gem = llm.setdefault("gemini", {})
    for key in ("model", "model_flash", "model_pro"):
        if gem.get(key):
            gem[key] = normalize_gemini_model(gem[key])


def models_to_try(primary: str) -> List[str]:
    primary = normalize_gemini_model(primary)
    ordered = [primary]
    for candidate in QUOTA_FALLBACK_CHAIN:
        if candidate not in ordered:
            ordered.append(candidate)
    return ordered


def format_gemini_error(exc: Exception, model: str) -> str:
    text = str(exc)
    if "429" in text or "RESOURCE_EXHAUSTED" in text:
        if "limit: 0" in text and "gemini-2.0-flash" in text:
            return (
                f"Gemini quota error for {model}: gemini-2.0-flash was retired on the free tier (limit 0). "
                f"Virtuoso now uses {DEFAULT_GEMINI_FLASH}. Run /gemini setup again or set "
                f"llm.gemini.model to {DEFAULT_GEMINI_FLASH} in virtuoso.yaml, then retry."
            )
        if "limit: 0" in text:
            return (
                f"Gemini quota error for {model}: your API key has no free-tier quota for this model. "
                f"Try /backend shimmy for local inference, enable billing in Google AI Studio, "
                f"or set llm.gemini.model to {DEFAULT_GEMINI_FLASH}."
            )
        return (
            f"Gemini rate limit (429) for {model}. Wait a minute and retry, or switch model via "
            f"llm.gemini.model in virtuoso.yaml."
        )
    if "503" in text or "UNAVAILABLE" in text:
        return (
            f"Gemini server busy (503) for {model}. Wait a moment and retry, or use /openai setup "
            f"for an alternative API (OpenRouter, Groq, etc.)."
        )
    return f"Gemini error ({model}): {text}"
