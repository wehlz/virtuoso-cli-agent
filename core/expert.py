#!/usr/bin/env python3
"""
core/expert.py
Google Gemini expert fallback integration (optional).
"""
import os
from typing import Optional, List, Tuple


class GeminiExpert:
    def __init__(self, api_key: Optional[str] = None, max_failures_before_fallback: int = 2):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.max_failures_before_fallback = max_failures_before_fallback
        self.failure_count = 0
        self.enabled = False
        self.genai = None

        if not self.api_key:
            # Not enabled if no key
            return

        try:
            import google.generativeai as genai
            self.genai = genai
            genai.configure(api_key=self.api_key)
            # model name used for generation
            self.model_name = "gemini-1.5-flash"
            self.enabled = True
        except Exception:
            # If the SDK is not installed or config fails, disable expert mode
            self.enabled = False

    def is_available(self) -> bool:
        return self.enabled and self.genai is not None

    def solve(self, task: str, local_attempts: List[Tuple[str, str]], context: str = "") -> Optional[str]:
        """Call Gemini to get a corrected solution for the task.

        local_attempts: list of tuples (code, error)
        """
        if not self.is_available():
            return None

        # Build a compact prompt
        attempts_text = "\n".join([f"Attempt:\n{c}\nError:\n{e}" for c, e in local_attempts]) if local_attempts else "(none)"
        prompt = f"Task: {task}\nContext: {context}\nLocal attempts:\n{attempts_text}\n\nAnalyze the attempts and provide corrected code. Output ONLY the corrected code in a markdown code block."

        try:
            # Use the SDK to generate content. The exact call may vary by SDK version.
            resp = self.genai.generate(model=self.model_name, prompt=prompt, max_output_tokens=1024)
            # Attempt to extract text
            text = ''
            if hasattr(resp, 'text'):
                text = resp.text
            elif isinstance(resp, dict):
                text = resp.get('text', '')
            else:
                text = str(resp)
            return self._extract_code(text)
        except Exception as e:
            print(f"Gemini fallback failed: {e}")
            return None

    def _extract_code(self, text: str) -> str:
        """Extract the first code block from markdown text, or return full text."""
        if "```" in text:
            parts = text.split("```")
            # find first non-empty code block
            for i in range(1, len(parts), 2):
                block = parts[i]
                # strip possible language spec
                if '\n' in block:
                    first_line, rest = block.split('\n', 1)
                    if first_line.strip().isalpha() or first_line.strip().startswith('python'):
                        return rest.strip()
                return block.strip()
        return text.strip()

    def reset(self):
        self.failure_count = 0
