#!/usr/bin/env python3
"""Measure basic generate latency (no tools, no multi-agent)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import load_config
from core.gemini_setup import has_gemini_api_key
from core.llm_client import get_llm_client


def main():
    config = load_config()
    llm_cfg = config.get("llm", {})
    if llm_cfg.get("backend", "").startswith("gemini") and not has_gemini_api_key(config):
        print("Set GEMINI_API_KEY or run /gemini setup before running latency tests.")
        return

    client = get_llm_client(llm_cfg)
    prompt = "Write a Python function to add two numbers."
    times = []
    runs = 3
    for i in range(runs):
        start = time.time()
        full = "".join(list(client.generate(prompt)))
        end = time.time()
        latency = end - start
        times.append(latency)
        print(f"Run {i + 1}: {latency:.2f}s ({len(full)} chars)")

    avg = sum(times) / len(times) if times else 0
    print(f"\nAverage latency (simple generate): {avg:.2f}s")


if __name__ == "__main__":
    main()
