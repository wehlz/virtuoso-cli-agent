# core/agents.py
"""
MapCoder-Lite multi-agent system.
All agents share the same LLM client but use distinct system prompts.
"""

from typing import Callable, List, Dict, Any, Optional

from core.base_llm_client import BaseLLMClient


class BaseAgent:
    def __init__(self, client: BaseLLMClient, name: str, system_prompt: str):
        self.client = client
        self.name = name
        self.system_prompt = system_prompt

    def run(self, prompt: str, temperature: Optional[float] = None) -> str:
        full = []
        for chunk in self.client.generate(prompt, system_prompt=self.system_prompt):
            full.append(chunk)
        return "".join(full).strip()


class PlannerAgent(BaseAgent):
    def __init__(self, client: BaseLLMClient):
        system = """You are a Planner agent. Your job is to break down a high-level software task into a concrete list of steps.
Each step must be specific, actionable, and verifiable. Output as a numbered list. Do not write code.
Focus on what needs to be done, not how.
Keep each step short (one sentence)."""
        super().__init__(client, "Planner", system)

    def plan(self, goal: str) -> List[str]:
        prompt = f"Break down the following goal into a numbered list of tasks (each task one sentence):\n{goal}"
        response = self.run(prompt)
        tasks = []
        for line in response.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() and '.' in line[:3]):
                task = line.split('.', 1)[-1].strip()
                tasks.append(task)
        if not tasks:
            tasks = [line for line in response.split('\n') if line.strip()]
        return tasks


class CoderAgent(BaseAgent):
    def __init__(self, client: BaseLLMClient):
        system = """You are a Coder agent. Your job is to write code for a specific task.
You will be given the task description, existing code context (if any), and requirements.
Output ONLY the code in a single markdown code block with language specification.
Do not include explanations. Use the exact file path as a comment at the top."""
        super().__init__(client, "Coder", system)

    def code(self, task: str, context: str = "", requirements: str = "") -> str:
        prompt = f"""Task: {task}
Existing code context:
{context if context else '(None)'}
Requirements to satisfy:
{requirements if requirements else '(None)'}
Generate the code changes. Output exactly as described."""
        return self.run(prompt, temperature=0.2)


class DebuggerAgent(BaseAgent):
    def __init__(self, client: BaseLLMClient):
        system = """You are a Debugger agent. You receive code and an error message (or test failure).
You must output a specific fix as a diff or full corrected code block.
Be precise. If no error, say 'NO_ERROR'."""
        super().__init__(client, "Debugger", system)

    def debug(self, code: str, error: str) -> str:
        prompt = f"""Code:
```python
{code}
```
Error:
{error}

Provide the corrected code in a markdown block. If no fix needed, output 'NO_ERROR'."""
        return self.run(prompt, temperature=0.3)


class ReviewerAgent(BaseAgent):
    def __init__(self, client: BaseLLMClient):
        system = """You are a Reviewer agent. You verify that code meets requirements.
Output a JSON-like summary with keys: \"PASS\" (true/false), \"ISSUES\" (list), \"SUGGESTIONS\" (list).
Be strict but fair."""
        super().__init__(client, "Reviewer", system)

    def review(self, code: str, requirements: str) -> Dict[str, Any]:
        prompt = f"""Code:
```python
{code}
```
Requirements:
{requirements}

Output a JSON object with exactly these fields:
- \"PASS\": boolean (true if code meets all requirements)
- \"ISSUES\": list of strings (problems found)
- \"SUGGESTIONS\": list of strings (improvements)
No other text."""
        response = self.run(prompt, temperature=0.1)
        import json
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end != 0:
                json_str = response[start:end]
                return json.loads(json_str)
        except Exception:
            pass
        return {"PASS": False, "ISSUES": ["Reviewer output malformed"], "SUGGESTIONS": []}


class Orchestrator:
    """Coordinates Planner, Coder, Debugger, Reviewer in a loop."""

    def __init__(self, client: BaseLLMClient):
        self.planner = PlannerAgent(client)
        self.coder = CoderAgent(client)
        self.debugger = DebuggerAgent(client)
        self.reviewer = ReviewerAgent(client)

    def build(
        self,
        goal: str,
        context: str = "",
        max_iterations: int = 3,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        if cancel_check and cancel_check():
            return {"error": "Cancelled by user", "plan": [], "code": "", "cancelled": True}

        print("🧠 Planning...")
        tasks = self.planner.plan(goal)
        if not tasks:
            return {"error": "Planner produced no tasks", "plan": [], "code": ""}

        print(f"📋 Plan: {len(tasks)} tasks")
        for i, t in enumerate(tasks, 1):
            print(f"  {i}. {t}")

        final_code = ""
        all_code = []
        review = {"PASS": False, "ISSUES": [], "SUGGESTIONS": []}

        completed_tasks = 0
        for idx, task in enumerate(tasks):
            if cancel_check and cancel_check():
                return {
                    "plan": tasks,
                    "code": final_code,
                    "review": review,
                    "success": False,
                    "partial": True,
                    "completed_tasks": completed_tasks,
                    "error": "Cancelled by user",
                    "cancelled": True,
                }
            print(f"\n💻 Task {idx+1}/{len(tasks)}: Coding...")
            try:
                code = self.coder.code(task, context=final_code, requirements=goal)
            except Exception as exc:
                return {
                    "plan": tasks,
                    "code": final_code,
                    "review": review,
                    "success": False,
                    "partial": True,
                    "completed_tasks": completed_tasks,
                    "error": str(exc),
                }
            if "```" in code:
                parts = code.split("```")
                if len(parts) >= 2:
                    code_block = parts[1]
                    if '\n' in code_block:
                        code_block = code_block.split('\n', 1)[-1]
                    code = code_block.strip()
            print("🔍 Reviewing...")
            try:
                review = self.reviewer.review(code, f"Task: {task}\nOverall goal: {goal}")
            except Exception as exc:
                return {
                    "plan": tasks,
                    "code": final_code,
                    "review": review,
                    "success": False,
                    "partial": True,
                    "completed_tasks": completed_tasks,
                    "error": str(exc),
                }
            if review.get("PASS", False):
                all_code.append(code)
                final_code = "\n\n".join(all_code)
                completed_tasks += 1
                print("✅ Task passed review.")
            else:
                print(f"⚠️ Issues: {review.get('ISSUES', [])}")
                try:
                    debug_fix = self.debugger.debug(code, str(review.get("ISSUES", [])))
                except Exception as exc:
                    return {
                        "plan": tasks,
                        "code": final_code,
                        "review": review,
                        "success": False,
                        "partial": True,
                        "completed_tasks": completed_tasks,
                        "error": str(exc),
                    }
                if debug_fix and "NO_ERROR" not in debug_fix:
                    if "```" in debug_fix:
                        parts = debug_fix.split("```")
                        if len(parts) >= 2:
                            debug_block = parts[1]
                            if '\n' in debug_block:
                                debug_block = debug_block.split('\n', 1)[-1]
                            debug_fix = debug_block.strip()
                    all_code.append(debug_fix)
                    final_code = "\n\n".join(all_code)
                    completed_tasks += 1
                    print("🛠️ Debugged and applied fix.")
                else:
                    print("❌ Could not auto-fix. Continuing.")
                    all_code.append(code)
                    final_code = "\n\n".join(all_code)
                    completed_tasks += 1

        return {
            "plan": tasks,
            "code": final_code,
            "review": review,
            "success": review.get("PASS", False),
            "partial": completed_tasks < len(tasks),
            "completed_tasks": completed_tasks,
        }
