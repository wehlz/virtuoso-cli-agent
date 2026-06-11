"""Hardware hints for 8GB-friendly defaults."""

from __future__ import annotations


def system_ram_gb() -> float | None:
    try:
        import psutil

        return psutil.virtual_memory().total / (1024**3)
    except Exception:
        return None


def is_low_memory_machine(threshold_gb: float = 12.0) -> bool:
    """True on typical 8GB laptops (and similar) — prefer Gemini cloud over local LLM."""
    ram = system_ram_gb()
    if ram is None:
        return True
    return ram < threshold_gb
