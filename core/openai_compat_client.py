"""OpenAI-compatible API client (OpenAI, OpenRouter, Groq, Together, etc.)."""

from __future__ import annotations

import os
from typing import Generator, Optional

from core.base_llm_client import BaseLLMClient


class OpenAICompatClient(BaseLLMClient):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 120.0,
    ):
        if not api_key:
            raise RuntimeError("API key not provided for OpenAI-compatible backend.")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install openai: pip install openai") from exc
        self._client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"), timeout=timeout)

    def _messages(self, prompt: str, system_prompt: Optional[str] = None) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=self._messages(prompt, system_prompt),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        for event in stream:
            if event.choices and event.choices[0].delta.content:
                yield event.choices[0].delta.content

    def generate_sync(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return "".join(self.generate(prompt, system_prompt=system_prompt))


def resolve_openai_api_key(cfg: dict) -> Optional[str]:
    key = (cfg.get("api_key") or "").strip()
    if key:
        return key
    for env_name in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY", "TOGETHER_API_KEY"):
        env_val = (os.environ.get(env_name) or "").strip()
        if env_val:
            return env_val
    return None
