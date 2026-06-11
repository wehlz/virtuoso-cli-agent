"""Gemini API key setup helpers (Option A — Google AI Studio API key)."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import yaml

from core.config import CONFIG_PATH, load_config
from core.gemini_models import DEFAULT_GEMINI_FLASH

GEMINI_KEY_URL = "https://aistudio.google.com/apikey"


def mask_api_key(key: str) -> str:
    if not key:
        return "(not set)"
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def _read_key_from_yaml(path) -> Optional[str]:
    try:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return (data.get("llm", {}).get("gemini", {}).get("api_key") or "").strip() or None
    except OSError:
        return None


def get_gemini_api_key(config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Read Gemini API key from config, env, or sibling dist/virtuoso.yaml."""
    if config is None:
        config = load_config()
    gem_cfg = config.get("llm", {}).get("gemini", {})
    key = (gem_cfg.get("api_key") or "").strip()
    if key:
        return key
    env_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if env_key:
        return env_key
    from core.paths import app_dir

    return _read_key_from_yaml(app_dir() / "dist" / "virtuoso.yaml")


def has_gemini_api_key(config: Optional[Dict[str, Any]] = None) -> bool:
    return get_gemini_api_key(config) is not None


def ensure_gemini_configured() -> bool:
    """Persist a usable Gemini key into virtuoso.yaml (from dist config or env)."""
    if has_gemini_api_key():
        key = get_gemini_api_key()
        if key and not (load_config().get("llm", {}).get("gemini", {}).get("api_key") or "").strip():
            save_gemini_api_key(key)
        return True
    from core.paths import app_dir

    dist_key = _read_key_from_yaml(app_dir() / "dist" / "virtuoso.yaml")
    if dist_key:
        save_gemini_api_key(dist_key)
        return True
    return False


def save_gemini_api_key(api_key: str, backend: str = "gemini-apikey") -> None:
    """Persist API key and switch backend to gemini-apikey in virtuoso.yaml."""
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("API key cannot be empty.")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        full = yaml.safe_load(f) or {}

    full.setdefault("llm", {})
    full["llm"]["backend"] = backend
    full["llm"].setdefault("fallback", "")
    full["llm"].setdefault("gemini", {})
    full["llm"]["gemini"]["auth_method"] = "apikey"
    full["llm"]["gemini"]["api_key"] = api_key
    if not full["llm"]["gemini"].get("model"):
        full["llm"]["gemini"]["model"] = DEFAULT_GEMINI_FLASH
        full["llm"]["gemini"]["model_flash"] = DEFAULT_GEMINI_FLASH

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(full, f, default_flow_style=False, sort_keys=False)

    os.environ["GEMINI_API_KEY"] = api_key


def prompt_for_api_key() -> Optional[str]:
    """Interactive prompt for a Gemini API key. Returns None if skipped."""
    import sys

    if not sys.stdin.isatty():
        return None

    print("\n--- Google Gemini Setup (Option A) ---")
    print(f"Get a free API key: {GEMINI_KEY_URL}")
    print("Press Enter to skip — you can run /gemini setup later or use /backend shimmy for local inference.\n")
    try:
        entered = input("Paste your Gemini API key: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return entered or None


def maybe_prompt_gemini_on_first_run() -> bool:
    """Prompt on first launch if no key is configured. Returns True if Gemini should be used."""
    config = load_config()
    if has_gemini_api_key(config):
        if _use_gemini_backend(config):
            return True
        # Key saved but backend still shimmy — prefer Gemini when a key exists
        ensure_gemini_backend_in_config()
        return True

    key = prompt_for_api_key()
    if not key:
        return False

    save_gemini_api_key(key)
    print(f"Gemini API key saved to {CONFIG_PATH}")
    return True


def _use_gemini_backend(config: Dict[str, Any]) -> bool:
    backend = config.get("llm", {}).get("backend", "")
    return backend in ("gemini-apikey", "gemini-flash", "gemini-pro", "gemini-oauth")


def ensure_gemini_backend_in_config() -> None:
    """Switch config to gemini-apikey when a key is available."""
    if not has_gemini_api_key():
        return
    config = load_config()
    if _use_gemini_backend(config):
        return
    key = get_gemini_api_key(config)
    if key:
        save_gemini_api_key(key)
