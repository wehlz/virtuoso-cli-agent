import os

from typing import Optional



from core.base_llm_client import BaseLLMClient

from core.gemini_client import GeminiAPIKeyClient, GeminiOAuthClient
from core.gemini_models import DEFAULT_GEMINI_FLASH, DEFAULT_GEMINI_PRO, resolve_gemini_model_from_config
from core.gemini_setup import get_gemini_api_key

from core.openai_compat_client import OpenAICompatClient, resolve_openai_api_key
from core.shimmy_client import ShimmyClient
from core.shimmy_manager import ensure_shimmy_running, resolve_shimmy_model





class ProxyLLMClient(BaseLLMClient):

    def __init__(

        self,

        primary: BaseLLMClient,

        fallback: Optional[BaseLLMClient] = None,

        primary_name: str = "primary",

        fallback_name: str = "fallback",

    ):

        self.primary = primary

        self.fallback = fallback

        self.primary_name = primary_name

        self.fallback_name = fallback_name



    def generate(self, prompt: str, system_prompt: Optional[str] = None):

        try:

            for chunk in self.primary.generate(prompt, system_prompt=system_prompt):

                yield chunk

        except Exception as e:

            print(f"LLM backend {self.primary_name} error: {e}")

            if self.fallback:

                print(f"Falling back to {self.fallback_name}")

                for chunk in self.fallback.generate(prompt, system_prompt=system_prompt):

                    yield chunk

            else:

                raise



    def generate_sync(self, prompt: str, system_prompt: Optional[str] = None) -> str:

        try:

            return "".join(list(self.primary.generate(prompt, system_prompt=system_prompt)))

        except Exception as e:

            print(f"LLM backend {self.primary_name} error: {e}")

            if self.fallback:

                print(f"Falling back to {self.fallback_name}")

                return "".join(list(self.fallback.generate(prompt, system_prompt=system_prompt)))

            raise





def _make_gemini_client(cfg: dict, backend: str) -> BaseLLMClient:

    gem_cfg = cfg.get("gemini", {})

    auth_method = gem_cfg.get("auth_method", "apikey")

    if backend == "gemini-oauth":

        auth_method = "oauth"

    elif backend == "gemini-apikey":

        auth_method = "apikey"



    model_name = resolve_gemini_model_from_config(gem_cfg, backend)



    if auth_method == "oauth":

        creds_path = gem_cfg.get("oauth_creds_path")

        return GeminiOAuthClient(model=model_name, oauth_creds_path=creds_path)



    api_key = get_gemini_api_key({"llm": cfg})

    return GeminiAPIKeyClient(api_key=api_key, model=model_name)





def _make_shimmy_client(cfg: dict) -> BaseLLMClient:

    shim_cfg = cfg.get("shimmy", {})

    port = shim_cfg.get("port", 8080)

    configured_model = shim_cfg.get("model", "auto")

    ensure_shimmy_running(shim_cfg)

    model = resolve_shimmy_model(

        port=port,

        configured=configured_model,

        preferred_path=shim_cfg.get("model_path"),

    )

    return ShimmyClient(model=model, port=port, timeout=300.0)


def _make_openai_client(cfg: dict) -> BaseLLMClient:
    oai_cfg = cfg.get("openai", {})
    api_key = resolve_openai_api_key(oai_cfg)
    if not api_key:
        raise RuntimeError(
            "No API key for OpenAI-compatible backend. Run /openai setup or set OPENAI_API_KEY."
        )
    return OpenAICompatClient(
        api_key=api_key,
        model=oai_cfg.get("model", "gpt-4o-mini"),
        base_url=oai_cfg.get("base_url", "https://api.openai.com/v1"),
        temperature=float(oai_cfg.get("temperature", 0.2)),
        max_tokens=int(oai_cfg.get("max_tokens", 4096)),
    )


def get_llm_client(cfg: dict) -> BaseLLMClient:

    """Factory to return an LLM client based on the `llm` config section."""

    backend = cfg.get("backend", "gemini-apikey")

    fallback = (cfg.get("fallback") or "").strip()



    if backend == "shimmy":

        try:

            primary = _make_shimmy_client(cfg)

        except Exception as e:

            if not fallback or fallback == "shimmy":

                raise RuntimeError(f"Shimmy backend failed: {e}") from e

            print(f"Shimmy backend failed: {e}")

            primary = None

    elif backend in ("gemini-flash", "gemini-pro", "gemini-apikey", "gemini-oauth"):

        primary = _make_gemini_client(cfg, backend)

    elif backend == "openai":

        primary = _make_openai_client(cfg)

    else:

        raise ValueError(

            f"Unknown llm backend: {backend}. Use gemini-apikey, openai, gemini-oauth, gemini-flash, gemini-pro, or shimmy."

        )



    if primary is None:

        if not fallback or fallback == backend:

            raise RuntimeError("Primary LLM backend failed and no valid fallback configured.")

        if fallback == "shimmy":

            return _make_shimmy_client(cfg)

        if fallback in ("gemini-flash", "gemini-pro", "gemini-apikey", "gemini-oauth"):

            return _make_gemini_client(cfg, fallback)

        if fallback == "openai":

            return _make_openai_client(cfg)

        raise RuntimeError(f"Fallback backend '{fallback}' is not supported.")



    fallback_client = None

    if fallback and fallback != backend:

        if fallback == "shimmy":

            try:

                fallback_client = _make_shimmy_client(cfg)

            except Exception as exc:

                print(f"Shimmy fallback unavailable: {exc}")

        elif fallback in ("gemini-flash", "gemini-pro", "gemini-apikey", "gemini-oauth"):

            try:

                fallback_client = _make_gemini_client(cfg, fallback)

            except Exception as exc:

                print(f"Gemini fallback unavailable: {exc}")

        elif fallback == "openai":

            try:

                fallback_client = _make_openai_client(cfg)

            except Exception as exc:

                print(f"OpenAI-compatible fallback unavailable: {exc}")



    if fallback_client:

        return ProxyLLMClient(

            primary=primary,

            fallback=fallback_client,

            primary_name=backend,

            fallback_name=fallback,

        )

    return primary


