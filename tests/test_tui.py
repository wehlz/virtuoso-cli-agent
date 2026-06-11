import pytest

import virtuoso as cli
from core import llm_client as llm_client_module
from virtuoso_tui import VirtuosoTUI


class DummyClient:
    def generate(self, prompt, system_prompt=None):
        yield "dummy"


def test_tui_action_bindings(monkeypatch):
    """Verify TUI actions are available and mapped to command behavior."""
    app = VirtuosoTUI()
    executed = []
    monkeypatch.setattr(app, "_execute_prompt", lambda: executed.append("prompt_sent"))
    app.action_send_prompt()
    assert executed == ["prompt_sent"]

    opened = []
    monkeypatch.setattr(app, "push_screen", lambda screen: opened.append(type(screen).__name__))
    app.action_open_settings()
    assert opened == ["SettingsModal"]


def test_backend_switch_updates_config(monkeypatch):
    """Verify backend switching updates the in-memory config without raising."""
    cli.config = {
        "llm": {
            "backend": "gemini-apikey",
            "fallback": "",
            "gemini": {
                "auth_method": "apikey",
                "api_key": "",
                "oauth_creds_path": "~/.gemini/oauth_creds.json",
                "model": "gemini-1.5-flash",
            },
        },
        "model": {"temperature": 0.2},
    }
    monkeypatch.setattr(llm_client_module, "get_llm_client", lambda cfg: DummyClient())
    cli.cmd_backend("gemini-apikey", api_key="TESTKEY", persist=False, ask_save=False)
    assert cli.config["llm"]["backend"] == "gemini-apikey"
    assert cli.config["llm"]["gemini"]["api_key"] == "TESTKEY"
    assert cli.config["llm"]["gemini"]["auth_method"] == "apikey"
