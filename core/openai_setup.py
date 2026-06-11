"""Setup helpers for OpenAI-compatible cloud backends."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import yaml

from core.config import CONFIG_PATH, load_config
from core.openai_compat_client import resolve_openai_api_key


PROVIDER_PRESETS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "key_url": "https://platform.openai.com/api-keys",
        "env": "OPENAI_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "key_url": "https://openrouter.ai/keys",
        "env": "OPENROUTER_API_KEY",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "key_url": "https://console.groq.com/keys",
        "env": "GROQ_API_KEY",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "key_url": "https://api.together.xyz/settings/api-keys",
        "env": "TOGETHER_API_KEY",
    },
}


def has_openai_api_key(config: Optional[Dict[str, Any]] = None) -> bool:
    config = config or load_config()
    oai = config.get("llm", {}).get("openai", {})
    return resolve_openai_api_key(oai) is not None


def save_openai_config(
    api_key: str,
    base_url: str,
    model: str,
    backend: str = "openai",
) -> None:
    config = load_config()
    llm = config.setdefault("llm", {})
    llm["backend"] = backend
    oai = llm.setdefault("openai", {})
    oai["api_key"] = api_key
    oai["base_url"] = base_url
    oai["model"] = model
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
    os.environ["OPENAI_API_KEY"] = api_key


def apply_provider_preset(name: str, api_key: str) -> None:
    preset = PROVIDER_PRESETS.get(name)
    if not preset:
        raise ValueError(f"Unknown provider preset: {name}")
    save_openai_config(api_key=api_key, base_url=preset["base_url"], model=preset["model"], backend="openai")
    env_name = preset.get("env")
    if env_name:
        os.environ[env_name] = api_key
