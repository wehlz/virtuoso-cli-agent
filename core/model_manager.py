"""Download and locate a small GGUF model that fits low-VRAM GPUs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests

from core.paths import models_dir

# ~379 MB — fits integrated GPUs on 8 GB laptops (avoids 2 GB VRAM buffer limits).
DEFAULT_MODEL_FILENAME = "Qwen2.5-Coder-0.5B-Instruct-Q4_K_M.gguf"
DEFAULT_MODEL_URL = (
    "https://huggingface.co/bartowski/Qwen2.5-Coder-0.5B-Instruct-GGUF/"
    "resolve/main/Qwen2.5-Coder-0.5B-Instruct-Q4_K_M.gguf"
)


def default_model_path() -> Path:
    return models_dir() / DEFAULT_MODEL_FILENAME


def model_id_from_path(path: Path) -> str:
    """Shimmy registers GGUF models using a lowercase id derived from the filename."""
    return path.stem.lower()


def locate_model(model_path: Optional[str] = None) -> Optional[Path]:
    if model_path:
        candidate = Path(model_path).expanduser()
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    candidate = default_model_path()
    if candidate.exists():
        return candidate
    return None


def ensure_default_model(force: bool = False) -> Path:
    """Download the bundled default model if it is missing."""
    target = default_model_path()
    if target.exists() and not force:
        return target

    models_dir().mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    headers = {}
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print(f"Downloading default model (~380 MB) to {target}...")
    print("This one-time download is sized for 8 GB laptops with integrated GPUs.")
    with requests.get(DEFAULT_MODEL_URL, headers=headers, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                fh.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    if pct % 10 == 0:
                        print(f"  {pct}%", end="\r", flush=True)

    if target.exists():
        target.unlink()
    tmp.replace(target)
    print(f"\nModel ready: {target}")
    return target
