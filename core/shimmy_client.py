from typing import Generator, Optional

import requests

from core.base_llm_client import BaseLLMClient


class ShimmyClient(BaseLLMClient):
    def __init__(
        self,
        model: str = "qwen2.5-coder:7b",
        port: int = 8080,
        api_key: str = "dummy",
        timeout: float = 180.0,
        max_tokens: int = 512,
    ):
        self.model = model
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}/v1"
        self.api_key = api_key
        self.timeout = timeout
        self.max_tokens = max_tokens
        self._client = self._create_client()

    def _create_client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai package is not installed. Install it with `pip install openai`."
            ) from exc

        try:
            return OpenAI(api_key=self.api_key, base_url=self.base_url)
        except Exception as exc:
            raise RuntimeError(f"Failed to create Shimmy OpenAI client: {exc}") from exc

    def _build_messages(self, prompt: str, system_prompt: Optional[str] = None) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _yield_from_stream(self, stream) -> Generator[str, None, None]:
        for event in stream:
            if event is None:
                continue
            if isinstance(event, str):
                yield event
                continue
            choice = None
            if isinstance(event, dict):
                choices = event.get("choices") or []
                if choices:
                    choice = choices[0]
            elif hasattr(event, "choices"):
                choices = getattr(event, "choices")
                if choices:
                    choice = choices[0]

            if choice:
                delta = choice.get("delta") if isinstance(choice, dict) else getattr(choice, "delta", None)
                if isinstance(delta, dict):
                    text = delta.get("content") or delta.get("text")
                    if text:
                        yield text
                        continue
                text = choice.get("text") if isinstance(choice, dict) else getattr(choice, "text", None)
                if text:
                    yield text

    def _generate_native(self, prompt: str) -> str:
        """Fallback to Shimmy's native /api/generate endpoint."""
        response = requests.post(
            f"http://127.0.0.1:{self.port}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "max_tokens": self.max_tokens,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            return payload.get("response") or payload.get("text") or ""
        return str(payload)

    def _generate_non_stream(self, messages: list[dict]) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            max_tokens=self.max_tokens,
            stream=False,
            timeout=self.timeout,
        )
        choice = response.choices[0] if response.choices else None
        if choice is None:
            return ""
        message = choice.message if hasattr(choice, "message") else None
        if message is None and isinstance(choice, dict):
            message = choice.get("message")
        if message is None:
            return ""
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
        return content or ""

    def generate(self, prompt: str, system_prompt: Optional[str] = None):
        messages = self._build_messages(prompt, system_prompt)
        combined_prompt = prompt if not system_prompt else f"{system_prompt}\n\n{prompt}"
        chunks: list[str] = []

        try:
            text = self._generate_non_stream(messages)
            if text:
                yield text
                return
        except Exception:
            pass

        try:
            stream = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=self.max_tokens,
                stream=True,
                timeout=self.timeout,
            )
            for text in self._yield_from_stream(stream):
                chunks.append(text)
                yield text
        except Exception as exc:
            if chunks:
                return
            try:
                fallback = self._generate_native(combined_prompt)
                if fallback:
                    yield fallback
                    return
            except Exception:
                pass
            raise RuntimeError(f"Shimmy error: {exc}") from exc

        if not chunks:
            try:
                fallback = self._generate_native(combined_prompt)
                if fallback:
                    yield fallback
                    return
            except Exception:
                pass
            raise RuntimeError(
                "Shimmy returned an empty response. Your GPU may not support local inference — "
                "try /gemini setup for Google Gemini, or /shimmy start after closing other GPU apps."
            )

    def generate_sync(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return "".join(self.generate(prompt, system_prompt=system_prompt))
