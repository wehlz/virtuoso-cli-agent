#!/usr/bin/env python3
"""
Virtuoso Benchmark Suite – Phase 6
Runs a subset of benchmark tasks and measures success rate, latency, and memory.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agents import Orchestrator
from core.config import load_config
from core.gemini_setup import has_gemini_api_key
from core.llm_client import get_llm_client

try:
    import psutil
except Exception:
    psutil = None


BENCH_TASKS = [
    {
        "id": "task_add",
        "description": "Write a Python function `add(a, b)` that returns the sum of two numbers.",
        "validation": "assert add(2,3)==5 and add(-1,1)==0",
        "expected_pass": True,
    },
    {
        "id": "task_factorial",
        "description": "Write a Python function `factorial(n)` that returns n! for n>=0 (use iterative or recursive).",
        "validation": "assert factorial(5)==120 and factorial(0)==1",
        "expected_pass": True,
    },
    {
        "id": "task_sum_squares",
        "description": "Write a function `sum_of_squares(nums)` that returns the sum of squares of a list of numbers.",
        "validation": "assert sum_of_squares([1,2,3])==14",
        "expected_pass": True,
    },
]


class BenchmarkRunner:
    def __init__(self):
        self.config = load_config()
        llm_cfg = self.config.get("llm", {})
        if llm_cfg.get("backend", "").startswith("gemini") and not has_gemini_api_key(self.config):
            raise RuntimeError("Set GEMINI_API_KEY or run /gemini setup before benchmarking.")
        self.client = get_llm_client(llm_cfg)
        self.orchestrator = Orchestrator(self.client)
        self.results: List[Dict[str, Any]] = []

    def _memory_mb(self) -> float:
        if psutil is None:
            return 0.0
        return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024

    def run_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        mem_before = self._memory_mb()
        result = self.orchestrator.build(task["description"])
        elapsed = time.time() - start
        mem_after = self._memory_mb()
        code = result.get("code", "")
        passed = False
        if code:
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
                fh.write(code)
                path = fh.name
            try:
                proc = subprocess.run(
                    [sys.executable, "-c", f"exec(open({path!r}).read()); {task['validation']}"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                passed = proc.returncode == 0
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    pass
        entry = {
            "id": task["id"],
            "passed": passed,
            "latency_s": round(elapsed, 2),
            "memory_mb": round(mem_after - mem_before, 2),
            "success": result.get("success", False),
        }
        self.results.append(entry)
        return entry

    def run_all(self, tasks: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
        for task in tasks or BENCH_TASKS:
            print(f"Running {task['id']}...")
            entry = self.run_task(task)
            print(f"  passed={entry['passed']} latency={entry['latency_s']}s")
        return self.results

    def summary(self) -> Dict[str, Any]:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("passed"))
        return {
            "total": total,
            "passed": passed,
            "pass_rate": round(passed / total, 3) if total else 0.0,
            "results": self.results,
        }


def main() -> int:
    runner = BenchmarkRunner()
    runner.run_all()
    summary = runner.summary()
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
