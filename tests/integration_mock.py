#!/usr/bin/env python3
"""
Integration smoke test using a mock LLM client so we can run end-to-end
flows (Planner -> Coder -> Reviewer -> Debugger) without a live backend.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agents import Orchestrator
from core.memory import ProjectMemory
from core.sandbox import LightweightSandbox


class MockLLMClient:
    def generate(self, prompt, system_prompt=None):
        if system_prompt and "Planner" in system_prompt:
            yield "STEP: Write the function definition for add.\n"
            yield "STEP: Add simple tests for add.\n"
            return
        if system_prompt and "Coder" in system_prompt:
            code = "```python\n# path: add.py\ndef add(a, b):\n    return a + b\n```\n"
            yield code
            return
        if system_prompt and "Reviewer" in system_prompt:
            if "def" in prompt or "def" in (system_prompt or ""):
                yield '{"PASS": true, "ISSUES": [], "SUGGESTIONS": []}'
            else:
                yield '{"PASS": false, "ISSUES": ["No function found"], "SUGGESTIONS": ["Add a def"]}'
            return
        if system_prompt and "Debugger" in system_prompt:
            yield "NO_ERROR"
            return
        if prompt.startswith("Problem:"):
            yield "STEP: Break down problem into small tasks.\n"
            yield "STEP: Implement core function.\n"
            yield "STEP: Add tests.\n"
            return
        yield "OK"


def run():
    print("Starting integration mock test")
    client = MockLLMClient()
    orch = Orchestrator(client)
    goal = "Write a Python function add(a,b) that returns sum of two numbers."
    result = orch.build(goal)
    print("\nOrchestrator result summary:")
    print("Plan:", result.get("plan"))
    print("Success:", result.get("success"))
    print("Code produced:\n", result.get("code"))

    code = result.get("code", "")
    if code:
        with LightweightSandbox(timeout_sec=5) as sb:
            print("\nRunning code in sandbox...")
            out, err, rc = sb.run_python(code)
            print("stdout:", out)
            print("stderr:", err)
            print("rc:", rc)

    pm = ProjectMemory(".")
    pm.add_to_history({"role": "test", "content": "integration ran"})
    print("\nRecent history sample:", pm.get_recent_history(2))


if __name__ == "__main__":
    run()
