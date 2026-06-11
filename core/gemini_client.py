import json

import os

import time

from pathlib import Path

from typing import Generator, Optional



import requests

from google.oauth2.credentials import Credentials

from google.auth.transport.requests import Request as AuthRequest



from core.base_llm_client import BaseLLMClient

from core.gemini_models import (

    DEFAULT_GEMINI_FLASH,

    format_gemini_error,

    models_to_try,

    normalize_gemini_model,

)



try:

    from google import genai

    from google.genai import types as genai_types

except Exception:

    genai = None

    genai_types = None





def load_oauth_credentials(oauth_creds_path: Optional[str] = None) -> Credentials:

    """Load Google OAuth credentials from a Gemini CLI credentials file."""

    creds_path = Path(oauth_creds_path or os.path.expanduser("~/.gemini/oauth_creds.json")).expanduser()

    if not creds_path.exists():

        raise RuntimeError(

            f"Gemini OAuth credentials not found at {creds_path}. Run `gemini auth login` and try again."

        )

    return Credentials.from_authorized_user_file(str(creds_path), scopes=["https://www.googleapis.com/auth/cloud-platform"])





def _is_quota_error(exc: Exception) -> bool:

    text = str(exc)

    return "429" in text or "RESOURCE_EXHAUSTED" in text


def _is_transient_error(exc: Exception) -> bool:

    text = str(exc)

    return "503" in text or "UNAVAILABLE" in text or "500" in text or "INTERNAL" in text





class GeminiAPIKeyClient(BaseLLMClient):

    def __init__(self, api_key: Optional[str], model: str = DEFAULT_GEMINI_FLASH, temperature: float = 0.2):

        if genai is None or genai_types is None:

            raise RuntimeError("google-genai is not installed. Install it with `pip install google-genai`.")

        if not api_key:

            raise RuntimeError("Gemini API key not provided")

        self.model = normalize_gemini_model(model)

        self.temperature = temperature

        self._client = genai.Client(api_key=api_key)



    def _stream_config(self, system_prompt: Optional[str] = None) -> "genai_types.GenerateContentConfig":

        kwargs = {"temperature": self.temperature}

        if system_prompt:

            kwargs["system_instruction"] = system_prompt

        return genai_types.GenerateContentConfig(**kwargs)



    def _extract_chunk_text(self, chunk) -> Optional[str]:

        text = getattr(chunk, "text", None)

        if text:

            return text

        candidates = getattr(chunk, "candidates", None) or []

        for candidate in candidates:

            content = getattr(candidate, "content", None)

            if content is None:

                continue

            parts = getattr(content, "parts", None) or []

            for part in parts:

                part_text = getattr(part, "text", None)

                if part_text:

                    return part_text

        return None



    def _stream_model(self, model: str, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                stream = self._client.models.generate_content_stream(
                    model=model,
                    contents=prompt,
                    config=self._stream_config(system_prompt),
                )
                for chunk in stream:
                    text = self._extract_chunk_text(chunk)
                    if text:
                        yield text
                return
            except Exception as exc:
                last_exc = exc
                if _is_transient_error(exc) and attempt < 2:
                    wait = 2 ** attempt
                    print(f"[Gemini: server busy, retrying in {wait}s...]")
                    time.sleep(wait)
                    continue
                raise
        if last_exc:
            raise last_exc



    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:

        last_exc: Optional[Exception] = None

        for model in models_to_try(self.model):

            try:

                if model != self.model:

                    print(f"[Gemini: retrying with {model}]")

                chunks = []

                for text in self._stream_model(model, prompt, system_prompt):

                    chunks.append(text)

                    yield text

                if chunks:

                    self.model = model

                    return

            except Exception as exc:

                last_exc = exc

                if _is_quota_error(exc):

                    continue

                raise RuntimeError(format_gemini_error(exc, model)) from exc



        if last_exc is not None:

            raise RuntimeError(format_gemini_error(last_exc, self.model)) from last_exc

        raise RuntimeError(f"Gemini returned no text for model {self.model}.")



    def generate_sync(self, prompt: str, system_prompt: Optional[str] = None) -> str:

        return "".join(self.generate(prompt, system_prompt=system_prompt))





class GeminiOAuthClient(BaseLLMClient):

    def __init__(

        self,

        model: str = DEFAULT_GEMINI_FLASH,

        oauth_creds_path: Optional[str] = None,

        temperature: float = 0.2,

    ):

        self.model = normalize_gemini_model(model)

        self.temperature = temperature

        self.oauth_creds_path = oauth_creds_path or os.path.expanduser("~/.gemini/oauth_creds.json")

        self.creds = load_oauth_credentials(self.oauth_creds_path)

        self._refresh_if_needed()



    def _refresh_if_needed(self):

        if not self.creds.valid:

            request = AuthRequest()

            self.creds.refresh(request)



    def _headers(self):

        self._refresh_if_needed()

        if not self.creds.token:

            raise RuntimeError("Failed to obtain OAuth access token for Gemini.")

        return {

            "Authorization": f"Bearer {self.creds.token}",

            "Content-Type": "application/json",

        }



    def _payload(self, prompt: str, system_prompt: Optional[str] = None) -> dict:

        contents = []

        if system_prompt:

            contents.append({"role": "user", "parts": [{"text": system_prompt}]})

        contents.append({"role": "user", "parts": [{"text": prompt}]})

        return {

            "contents": contents,

            "generationConfig": {"temperature": self.temperature},

        }



    def _extract_text(self, event: dict) -> Optional[str]:

        if not isinstance(event, dict):

            return None

        if "candidates" in event and isinstance(event["candidates"], list) and event["candidates"]:

            candidate = event["candidates"][0]

            if isinstance(candidate, dict):

                content = candidate.get("content")

                if isinstance(content, dict):

                    parts = content.get("parts") or []

                    if parts and isinstance(parts[0], dict):

                        return parts[0].get("text")

                    return content.get("text")

                if isinstance(content, str):

                    return content

        if "text" in event:

            return event.get("text")

        if "content" in event:

            return event.get("content")

        return None



    def _stream_model(self, model: str, prompt: str, system_prompt: Optional[str] = None):

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"

        headers = self._headers()

        payload = self._payload(prompt, system_prompt=system_prompt)

        response = requests.post(url, headers=headers, json=payload, stream=True, timeout=120)

        if response.status_code >= 400:

            raise RuntimeError(f"Gemini OAuth request failed: {response.status_code} {response.text}")

        for raw_line in response.iter_lines(decode_unicode=True):

            if not raw_line:

                continue

            line = raw_line.strip()

            if line == "[DONE]":

                break

            if line.startswith("data:"):

                line = line[len("data:") :].strip()

            if not line:

                continue

            try:

                event = json.loads(line)

            except json.JSONDecodeError:

                continue

            text = self._extract_text(event)

            if text:

                yield text



    def generate(self, prompt: str, system_prompt: Optional[str] = None):

        last_exc: Optional[Exception] = None

        for model in models_to_try(self.model):

            try:

                if model != self.model:

                    print(f"[Gemini: retrying with {model}]")

                chunks = []

                for text in self._stream_model(model, prompt, system_prompt):

                    chunks.append(text)

                    yield text

                if chunks:

                    self.model = model

                    return

            except Exception as exc:

                last_exc = exc

                if _is_quota_error(exc):

                    continue

                raise RuntimeError(format_gemini_error(exc, model)) from exc



        if last_exc is not None:

            raise RuntimeError(format_gemini_error(last_exc, self.model)) from last_exc

        raise RuntimeError(f"Gemini returned no text for model {self.model}.")



    def generate_sync(self, prompt: str, system_prompt: Optional[str] = None) -> str:

        return "".join(self.generate(prompt, system_prompt=system_prompt))


