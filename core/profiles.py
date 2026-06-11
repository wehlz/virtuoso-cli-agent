"""Runtime profiles: cloud (Gemini), local (Shimmy), offline (Shimmy only)."""

from __future__ import annotations

from typing import Any, Dict, List

import yaml

from core.config import CONFIG_PATH

PROFILE_NAMES = ("cloud", "local", "offline")

PROFILE_SETTINGS: Dict[str, Dict[str, Any]] = {
    "cloud": {
        "llm": {"backend": "gemini-apikey"},
    },
    "local": {
        "llm": {"backend": "shimmy"},
    },
    "offline": {
        "llm": {"backend": "shimmy"},
    },
}


def list_profiles() -> List[str]:
    return list(PROFILE_NAMES)


def apply_profile(name: str, persist: bool = True) -> Dict[str, Any]:
    """Apply a named profile to virtuoso.yaml."""
    key = name.strip().lower()
    if key not in PROFILE_SETTINGS:
        raise ValueError(f"Unknown profile '{name}'. Choose: {', '.join(PROFILE_NAMES)}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        full = yaml.safe_load(f) or {}

    patch = PROFILE_SETTINGS[key]
    llm = full.setdefault("llm", {})
    llm.update(patch.get("llm", {}))
    full.setdefault("cli", {})["active_profile"] = key

    shim = full.setdefault("llm", {}).setdefault("shimmy", {})
    if key == "cloud":
        shim["auto_start"] = False
        shim["auto_download_model"] = False
    elif key in ("local", "offline"):
        shim["auto_start"] = True
        shim["auto_download_model"] = True

    if persist:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(full, f, default_flow_style=False, sort_keys=False)

    return full


def active_profile(config: Dict[str, Any]) -> str:
    return config.get("cli", {}).get("active_profile", "cloud")
