import yaml

from pathlib import Path

from typing import Any, Dict



from core.gemini_models import apply_gemini_model_defaults
from core.paths import config_path as _config_path



CONFIG_PATH = _config_path()


def default_config() -> Dict[str, Any]:
    return {
        "model": {"temperature": 0.2, "max_tokens": 2048},
        "cli": {
            "history_file": ".virtuoso/history.json",
            "log_dir": ".virtuoso/logs",
            "max_conversation_exchanges": 10,
            "active_profile": "cloud",
            "ide_server_port": 8765,
            "low_memory_mode": True,
        },
        "sandbox": {"enabled": True, "type": "lightweight"},
        "performance": {"cache_size_mb": 256, "max_context_lines": 500},
        "expert": {
            "enabled": True,
            "gemini_api_key": "",
            "max_failures_before_fallback": 2,
        },
        "llm": {
            "backend": "gemini-apikey",
            "fallback": "",
            "shimmy": {
                "enabled": True,
                "port": 8080,
                "binary_path": "",
                "auto_start": False,
                "model": "auto",
                "model_path": "virtuoso_data/models/Qwen2.5-Coder-0.5B-Instruct-Q4_K_M.gguf",
                "auto_download_model": False,
                "extra_args": ["--kv-quant", "int4", "--ctx", "1024", "--prefill-chunk", "8"],
            },
            "gemini": {
                "auth_method": "apikey",
                "api_key": "",
                "oauth_creds_path": "~/.gemini/oauth_creds.json",
                "model": "gemini-2.5-flash",
                "model_flash": "gemini-2.5-flash",
                "model_pro": "gemini-2.5-pro",
            },
            "openai": {
                "api_key": "",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
                "temperature": 0.2,
                "max_tokens": 4096,
            },
        },
    }





def resolve_backend(config: Dict[str, Any]) -> str:

    """Resolve backend: Gemini by default; Shimmy only when explicitly configured."""

    llm = config.get("llm", {})

    backend = (llm.get("backend") or "gemini-apikey").strip()



    if backend in ("auto", "qwen"):

        return "gemini-apikey"



    return backend





def load_config() -> Dict[str, Any]:

    path = _config_path()

    if not path.exists():
        config = default_config()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
        except OSError:
            pass
        apply_gemini_model_defaults(config)
        return config

    with open(path, "r", encoding="utf-8") as f:

        config = yaml.safe_load(f) or {}

    apply_gemini_model_defaults(config)

    llm = config.setdefault("llm", {})

    llm["backend"] = resolve_backend(config)

    return config





def load_llm_config() -> Dict[str, Any]:

    conf = load_config()

    return conf.get("llm", {})





def load_shimmy_config() -> Dict[str, Any]:

    conf = load_config()

    return conf.get("llm", {}).get("shimmy", {})


