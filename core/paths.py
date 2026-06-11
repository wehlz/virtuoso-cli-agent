"""Resolve application paths for dev and PyInstaller frozen executables."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def app_dir() -> Path:
    """Writable directory beside the executable (frozen) or project root (dev)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """Bundled read-only resources (PyInstaller extract dir or project root)."""
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    """User config in app_dir, falling back to bundled virtuoso.yaml."""
    user_cfg = app_dir() / "virtuoso.yaml"
    if user_cfg.exists():
        return user_cfg
    bundled = resource_dir() / "virtuoso.yaml"
    if bundled.exists() and bundled != user_cfg:
        try:
            shutil.copy2(bundled, user_cfg)
        except OSError:
            return bundled
        return user_cfg
    return user_cfg


def data_dir() -> Path:
    return app_dir() / "virtuoso_data"


def shimmy_dir() -> Path:
    return data_dir() / "shimmy"


def models_dir() -> Path:
    return data_dir() / "models"
