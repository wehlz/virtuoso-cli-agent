"""Interactive first-run wizard."""

from __future__ import annotations

import sys
from pathlib import Path

from core.gemini_setup import GEMINI_KEY_URL, has_gemini_api_key, prompt_for_api_key, save_gemini_api_key
from core.hardware import is_low_memory_machine, system_ram_gb
from core.paths import app_dir
from core.profiles import apply_profile


def _marker_path() -> Path:
    return app_dir() / ".virtuoso" / "onboarding_complete"


def onboarding_complete() -> bool:
    return _marker_path().exists()


def mark_onboarding_complete() -> None:
    path = _marker_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ok\n", encoding="utf-8")


def run_onboarding_wizard() -> None:
    if not sys.stdin.isatty():
        return
    if onboarding_complete():
        return

    ram = system_ram_gb()
    ram_note = f" ({ram:.0f} GB RAM detected)" if ram else ""
    low_mem = is_low_memory_machine()

    print("\n=== Welcome to Virtuoso ===")
    print("Terminal coding agent — chat, plan, build, and IDE integration.\n")

    if low_mem:
        print(f"Low-memory mode{ram_note}: using Google Gemini in the cloud (best on 8GB laptops).")
        print("Local AI (Shimmy) is available later via /profile local — needs a strong GPU.\n")
        apply_profile("cloud", persist=True)
        if not has_gemini_api_key():
            print(f"Get a free API key: {GEMINI_KEY_URL}")
            key = prompt_for_api_key()
            if key:
                save_gemini_api_key(key)
                print("Gemini configured.")
        mark_onboarding_complete()
        _print_next_steps()
        return

    print("Choose a profile:")
    print("  1) Cloud — Google Gemini (recommended)")
    print("  2) Local  — Shimmy on this machine")
    print("  3) Skip   — configure later")
    try:
        choice = input("Choice [1]: ").strip() or "1"
    except (EOFError, KeyboardInterrupt):
        print()
        mark_onboarding_complete()
        return

    if choice == "2":
        apply_profile("local", persist=True)
        print("Profile: local. Run /shimmy install then /shimmy start when ready.")
    elif choice == "1":
        apply_profile("cloud", persist=True)
        if not has_gemini_api_key():
            key = prompt_for_api_key()
            if key:
                save_gemini_api_key(key)
    else:
        apply_profile("cloud", persist=True)

    mark_onboarding_complete()
    _print_next_steps()


def _print_next_steps() -> None:
    print("\n--- You're ready ---")
    print("  • Type a question at >  (chat with memory)")
    print("  • /gemini setup        (Google) or /openai setup (OpenRouter, Groq, etc.)")
    print("  • /plan, /build, /fix, /explain")
    print("  • python virtuoso.py --dashboard   (browser UI)")
    print("  • python virtuoso.py --serve   (for VS Code / Cursor + Continue)")
    print("  • /status              (check backend)\n")
