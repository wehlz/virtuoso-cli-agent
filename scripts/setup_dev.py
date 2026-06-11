#!/usr/bin/env python3
"""Create a local development environment for Virtuoso."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / ".venv"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def ensure_venv() -> Path:
    if not venv_python().exists():
        print(f"Creating virtual environment at {VENV_DIR}")
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    return venv_python()


def ensure_config() -> None:
    target = ROOT / "virtuoso.yaml"
    source = ROOT / "virtuoso.yaml.example"
    if target.exists() or not source.exists():
        return
    shutil.copy2(source, target)
    print("Created virtuoso.yaml from virtuoso.yaml.example")


def main() -> int:
    py = ensure_venv()
    run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(py), "-m", "pip", "install", "-e", ".[dev]"])
    ensure_config()

    print("\nVirtuoso development setup complete.")
    if os.name == "nt":
        print(r"Activate: .venv\Scripts\activate")
    else:
        print("Activate: source .venv/bin/activate")
    print("Run:      python virtuoso.py --dashboard")
    print("Check:    python virtuoso.py --doctor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
