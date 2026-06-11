import os
from pathlib import Path

import yaml

from core import gemini_setup


def test_mask_api_key():
    assert gemini_setup.mask_api_key("abcdefghijklmnop") == "abcd...mnop"
    assert gemini_setup.mask_api_key("") == "(not set)"


def test_save_and_load_gemini_api_key(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "virtuoso.yaml"
    cfg_file.write_text(yaml.safe_dump({"llm": {"backend": "shimmy", "gemini": {"api_key": ""}}}))
    monkeypatch.setattr(gemini_setup, "CONFIG_PATH", cfg_file)

    gemini_setup.save_gemini_api_key("test-api-key-12345")
    loaded = yaml.safe_load(cfg_file.read_text())

    assert loaded["llm"]["backend"] == "gemini-apikey"
    assert loaded["llm"]["gemini"]["api_key"] == "test-api-key-12345"
    assert os.environ.get("GEMINI_API_KEY") == "test-api-key-12345"
    assert gemini_setup.get_gemini_api_key(loaded) == "test-api-key-12345"
