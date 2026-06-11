import os
import socket
import subprocess
import sys
import types
from pathlib import Path

import pytest

from core import shimmy_manager
from core.shimmy_client import ShimmyClient


class DummyResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code


class DummyProcess:
    def __init__(self):
        self.terminated = False
        self.killed = False
        self._poll = None

    def poll(self):
        return self._poll

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        self._poll = 0

    def kill(self):
        self.killed = True


def test_find_shimmy_binary_with_explicit_path(tmp_path):
    binary = tmp_path / ("shimmy.exe" if sys.platform.startswith("win") else "shimmy")
    binary.write_text("dummy")
    binary.chmod(0o755)
    found = shimmy_manager.find_shimmy_binary(str(binary))
    assert found == binary


def test_find_shimmy_binary_searches_bin_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(shimmy_manager, "shimmy_dir", lambda: tmp_path / "missing_shimmy")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    binary = bin_dir / ("shimmy.exe" if sys.platform.startswith("win") else "shimmy")
    binary.write_text("dummy")
    binary.chmod(0o755)
    found = shimmy_manager.find_shimmy_binary()
    assert found == binary


def test_is_shimmy_running_returns_false_on_connect_error(monkeypatch):
    def fake_get(*args, **kwargs):
        raise Exception("connection refused")

    monkeypatch.setattr(shimmy_manager.requests, "get", fake_get)
    assert shimmy_manager.is_shimmy_running(port=9999) is False


def test_start_shimmy_raises_when_binary_missing(monkeypatch):
    monkeypatch.setattr(shimmy_manager, "find_shimmy_binary", lambda binary_path=None: None)
    with pytest.raises(RuntimeError, match="Shimmy binary not found"):
        shimmy_manager.start_shimmy(port=9999, model="qwen2.5-coder:7b")


def test_stop_shimmy_terminates_managed_process(monkeypatch):
    proc = DummyProcess()
    proc._poll = None
    monkeypatch.setattr(shimmy_manager, "_SHIMMY_PROCESS", proc)
    shimmy_manager.stop_shimmy()
    assert proc.terminated
    assert proc._poll == 0


def test_install_shimmy_help_contains_cargo():
    help_text = shimmy_manager.install_shimmy_help()
    assert "cargo install shimmy" in help_text
    assert "virtuoso_data" in help_text


def test_shimmy_client_streaming(monkeypatch):
    dummy_openai = types.ModuleType("openai")

    class DummyMessage:
        content = ""

    class DummyChoice:
        message = DummyMessage()

    class DummyResponse:
        choices = [DummyChoice()]

    class DummyChat:
        class completions:
            @staticmethod
            def create(model, messages, temperature, stream, timeout, max_tokens=None, **kwargs):
                if not stream:
                    return DummyResponse()
                yield {"choices": [{"delta": {"content": "hello"}}]}
                yield {"choices": [{"delta": {"content": " world"}}]}

    class DummyOpenAIClient:
        def __init__(self, api_key=None, base_url=None):
            self.chat = DummyChat()

    dummy_openai.OpenAI = DummyOpenAIClient
    monkeypatch.setitem(sys.modules, "openai", dummy_openai)

    client = ShimmyClient(model="qwen2.5-coder:7b", port=8080)
    result = list(client.generate("hi", system_prompt="say hi"))
    assert result == ["hello", " world"]
    assert client.generate_sync("hi") == "hello world"


def test_shimmy_client_raises_without_openai(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)
    with pytest.raises(RuntimeError, match="openai package is not installed"):
        ShimmyClient(model="qwen2.5-coder:7b", port=8080)


def test_shimmy_cli_install_command_output():
    result = subprocess.run(
        [sys.executable, "-c", "from virtuoso import cmd_shimmy_install; cmd_shimmy_install()"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Shimmy installed at:" in result.stdout or "cargo install shimmy" in result.stdout


def _get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_find_shimmy_binary_checks_virtuoso_data(tmp_path, monkeypatch):
    shim_dir = tmp_path / "shimmy"
    monkeypatch.setattr(shimmy_manager, "shimmy_dir", lambda: shim_dir)
    shim_dir.mkdir(parents=True)
    binary = shim_dir / ("shimmy.exe" if sys.platform.startswith("win") else "shimmy")
    binary.write_text("dummy")
    binary.chmod(0o755)
    found = shimmy_manager.find_shimmy_binary()
    assert found == binary.resolve()


@pytest.mark.skipif(shimmy_manager.find_shimmy_binary() is None, reason="Shimmy binary is not installed")
def test_shimmy_integration_start_stop():
    port = _get_free_port()
    binary = shimmy_manager.find_shimmy_binary()
    shim_cfg = {
        "port": port,
        "model": "auto",
        "binary_path": str(binary),
        "enabled": True,
        "auto_download_model": False,
    }
    try:
        proc = shimmy_manager.start_shimmy(port=port, model="auto", binary_path=str(binary), config=shim_cfg)
        assert shimmy_manager.is_shimmy_running(port)
    finally:
        if proc:
            shimmy_manager.stop_shimmy()
        assert shimmy_manager.is_shimmy_running(port) is False
