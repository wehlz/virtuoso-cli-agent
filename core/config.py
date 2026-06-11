import yaml

from pathlib import Path

from typing import Any, Dict



from core.gemini_models import apply_gemini_model_defaults
from core.paths import config_path as _config_path



CONFIG_PATH = _config_path()





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

        raise FileNotFoundError(

            f"virtuoso.yaml not found at {path}. Copy the bundled config beside the executable."

        )

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


