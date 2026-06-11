#!/usr/bin/env python3
"""
core/memory.py
Persistent project memory and summarization utilities for Virtuoso.
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class ProjectMemory:
    """Manages persistent project state and constitution."""
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.memory_dir = self.project_root / ".virtuoso"
        self.memory_dir.mkdir(exist_ok=True)
        self.constitution_path = self.memory_dir / "constitution.md"
        self.state_path = self.memory_dir / "state.json"

    def load_constitution(self) -> str:
        """Load project constitution (coding standards, architecture notes)."""
        if self.constitution_path.exists():
            return self.constitution_path.read_text(encoding="utf-8")
        default = """# Virtuoso Project Constitution

## Core Principles
- Write clean, maintainable code.
- Follow language-specific best practices.
- Include error handling for critical operations.

## Architecture Preferences
- Prefer modular design.
- Keep functions small and focused.
- Document public APIs.

## Agent Behavior
- Ask for clarification when requirements are ambiguous.
- Prefer iterative, testable changes.
"""
        self.constitution_path.write_text(default, encoding="utf-8")
        return default

    def update_constitution(self, content: str):
        """Overwrite constitution."""
        self.constitution_path.write_text(content, encoding="utf-8")

    def load_state(self) -> Dict[str, Any]:
        """Load persistent state (last plan, recent actions, etc.)."""
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:
                return {"history": [], "last_code": "", "preferences": {}}
        return {"history": [], "last_code": "", "preferences": {}}

    def save_state(self, state: Dict[str, Any]):
        """Save state."""
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def add_to_history(self, entry: Dict[str, Any], max_entries: int = 50):
        """Add an entry to conversation history (rolling)."""
        state = self.load_state()
        history = state.get("history", [])
        history.append(entry)
        if len(history) > max_entries:
            history = history[-max_entries:]
        state["history"] = history
        self.save_state(state)

    def get_recent_history(self, n: int = 10) -> List[Dict[str, Any]]:
        state = self.load_state()
        return state.get("history", [])[-n:]


class SlidingWindowSummarizer:
    """
    Compresses long conversation history or code context into a shorter summary.
    Uses the model itself (via a provided client) to summarize when threshold exceeded.
    """
    def __init__(self, client, max_tokens: int = 4000, summary_trigger: int = 3000):
        self.client = client
        self.max_tokens = max_tokens
        self.summary_trigger = summary_trigger

    def estimate_tokens(self, text: str) -> int:
        """Rough estimate: 1 token ~4 chars for English code."""
        return max(1, len(text) // 4)

    def summarize(self, text: str, max_summary_tokens: int = 500) -> str:
        """Summarize long text using the model."""
        prompt = f"Summarize the following text concisely, keeping key information:\n\n{text}\n\nSummary:"
        response = []
        for chunk in self.client.generate(prompt, temperature=0.3):
            response.append(chunk)
        summary = ''.join(response).strip()
        if self.estimate_tokens(summary) > max_summary_tokens:
            lines = summary.split('\n')
            summary = '\n'.join(lines[:10])
        return summary

    def compress_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Compress history list into fewer entries by merging and summarizing."""
        text = '\n'.join([f"{e.get('role','')}: {e.get('content','')}" for e in history])
        total_tokens = self.estimate_tokens(text)
        if total_tokens > self.summary_trigger:
            summary = self.summarize(text, max_summary_tokens=500)
            # Return last 5 entries plus a summary entry
            tail = history[-5:] if len(history) > 5 else history
            return [{"role": "system", "content": f"SUMMARY: {summary}"}] + tail
        return history
