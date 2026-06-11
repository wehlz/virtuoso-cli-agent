import copy
from typing import List, Optional
from core.base_llm_client import BaseLLMClient


class ThoughtNode:
    def __init__(self, content: str, parent=None):
        self.content = content
        self.parent = parent
        self.children = []
        self.value = 0.0


class TreeOfThoughts:
    def __init__(self, client: BaseLLMClient, max_depth: int = 3, width: int = 3, eval_threshold: float = 0.5):
        self.client = client
        self.max_depth = max_depth
        self.width = width
        self.eval_threshold = eval_threshold

    def generate_thoughts(self, problem: str, current_thoughts: List[str]) -> List[str]:
        prompt = f"""Problem: {problem}
Current reasoning steps:
{chr(10).join(f'- {t}' for t in current_thoughts)}
Based on the above, propose {self.width} distinct next steps to solve the problem.
Output each step on a new line starting with \"STEP:\". Keep each step short (one sentence).
"""
        response = []
        for chunk in self.client.generate(prompt):
            response.append(chunk)
        full = ''.join(response)
        steps = []
        for line in full.split('\n'):
            if line.startswith("STEP:"):
                steps.append(line[5:].strip())
        return steps[:self.width]

    def evaluate_thought(self, problem: str, thought: str) -> float:
        positive = {"correct", "solved", "works", "success", "good"}
        negative = {"error", "wrong", "failed", "incorrect", "problem"}
        score = 0.5
        low = thought.lower()
        if any(p in low for p in positive):
            score += 0.3
        if any(n in low for n in negative):
            score -= 0.4
        return max(0.0, min(1.0, score))

    def search(self, problem: str, initial_thought: str = "") -> Optional[ThoughtNode]:
        root = ThoughtNode(initial_thought if initial_thought else "Start")
        return self._dfs(root, problem, 0)

    def _dfs(self, node: ThoughtNode, problem: str, depth: int) -> Optional[ThoughtNode]:
        if depth >= self.max_depth:
            node.value = self.evaluate_thought(problem, node.content)
            return node if node.value > self.eval_threshold else None

        path = []
        cur = node
        while cur.parent:
            path.insert(0, cur.content)
            cur = cur.parent
        path.insert(0, cur.content)

        candidates = self.generate_thoughts(problem, path)
        best_leaf = None
        best_value = -1.0
        for cand in candidates:
            child = ThoughtNode(cand, parent=node)
            child.value = self.evaluate_thought(problem, cand)
            if child.value < self.eval_threshold:
                continue
            node.children.append(child)
            result = self._dfs(child, problem, depth + 1)
            if result and result.value > best_value:
                best_leaf = result
                best_value = result.value

        if best_leaf:
            return best_leaf

        # If no child produced a valid leaf, allow a high-value current node at max depth-1.
        if depth == self.max_depth - 1 and node.value > self.eval_threshold:
            return node

        return None

    def get_path(self, node: ThoughtNode) -> List[str]:
        path = []
        cur = node
        while cur:
            path.insert(0, cur.content)
            cur = cur.parent
        return path
