from core.gemini_models import (
    DEFAULT_GEMINI_FLASH,
    apply_gemini_model_defaults,
    normalize_gemini_model,
)


def test_normalize_deprecated_2_0_flash():
    assert normalize_gemini_model("gemini-2.0-flash") == DEFAULT_GEMINI_FLASH


def test_apply_defaults_rewrites_config():
    config = {"llm": {"gemini": {"model": "gemini-2.0-flash", "model_flash": "gemini-2.0-flash"}}}
    apply_gemini_model_defaults(config)
    assert config["llm"]["gemini"]["model"] == DEFAULT_GEMINI_FLASH
