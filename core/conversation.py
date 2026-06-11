"""Build conversation-aware prompts for multi-turn CLI chat."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_conversation_prompt(
    user_input: str,
    history: List[Dict[str, str]],
    max_exchanges: int = 10,
) -> str:
    """Format prior turns plus the current user message for any LLM backend."""
    max_entries = max(1, max_exchanges) * 2
    recent = history[-max_entries:]
    if not recent:
        return user_input

    lines = ["Previous conversation:"]
    for message in recent:
        role = "User" if message.get("role") == "user" else "Assistant"
        lines.append(f"{role}: {message.get('content', '')}")
    lines.append(f"\nCurrent query: {user_input}")
    return "\n".join(lines)


def max_conversation_exchanges(config: Optional[Dict[str, Any]] = None, default: int = 10) -> int:
    if not config:
        return default
    cli_cfg = config.get("cli", {})
    try:
        return int(cli_cfg.get("max_conversation_exchanges", default))
    except (TypeError, ValueError):
        return default
