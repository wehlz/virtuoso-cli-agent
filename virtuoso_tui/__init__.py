import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Select, Static, TextArea
from textual import work

# TODO: Display a small Virtuoso ASCII art logo or banner here in the TUI using rich in the future.
import virtuoso as cli


class NewLogEntry(Message):
    def __init__(self, sender, text: str) -> None:
        super().__init__(sender)
        self.text = text


class ReasoningStep(Message):
    def __init__(self, sender, step: str) -> None:
        super().__init__(sender)
        self.step = step


class BackendChanged(Message):
    def __init__(self, sender, backend: str, model: str) -> None:
        super().__init__(sender)
        self.backend = backend
        self.model = model


class SettingsSaved(Message):
    def __init__(self, sender, payload: dict) -> None:
        super().__init__(sender)
        self.payload = payload


class SettingsCancelled(Message):
    pass


class TUIOutputStream:
    def __init__(self, app: App):
        self.app = app
        self._buffer = ""

    def write(self, text: str) -> None:
        if not text:
            return
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._emit_line(line)

    def flush(self) -> None:
        if self._buffer:
            self._emit_line(self._buffer)
            self._buffer = ""

    def _emit_line(self, line: str) -> None:
        line = line.rstrip()
        if not line:
            return
        message = ReasoningStep(self.app, line) if line.startswith(("🧠", "📋", "💻", "🔍", "✅", "⚠️", "🛠️", "❌")) else NewLogEntry(self.app, line)
        self.app.call_from_thread(self.app.post_message, message)


class SettingsModal(ModalScreen):
    BINDINGS = [("escape", "app.pop_screen", "Close")]

    def compose(self) -> ComposeResult:
        llm_cfg = cli.config.get("llm", {})
        gem_cfg = llm_cfg.get("gemini", {})
        backend = llm_cfg.get("backend", "gemini-apikey")
        api_key = gem_cfg.get("api_key", "")
        oauth_path = gem_cfg.get("oauth_creds_path", "~/.gemini/oauth_creds.json")
        model = gem_cfg.get("model", gem_cfg.get("model_flash", "gemini-2.0-flash"))
        shim_cfg = llm_cfg.get("shimmy", {})
        shim_model_path = shim_cfg.get("model_path", "")

        yield Static("Virtuoso Settings", classes="modal-title")
        yield Select(
            options=[
                ("gemini-apikey", "Gemini API Key"),
                ("gemini-oauth", "Gemini OAuth"),
                ("shimmy", "Shimmy (local)"),
            ],
            value=backend,
            id="backend-select",
        )
        yield Select(
            options=[("gemini-2.0-flash", "Gemini 2.0 Flash"), ("gemini-2.5-pro", "Gemini 2.5 Pro")],
            value=model,
            id="gemini-model",
        )
        yield Input(value=api_key, id="gemini-api-key", placeholder="Gemini API Key")
        yield Input(value=oauth_path, id="gemini-oauth-path", placeholder="Gemini OAuth creds path")
        yield Label("OAuth will use your personal Google account. Google may collect prompts/code for improvement.", id="oauth-warning")
        yield Input(value=shim_model_path, id="shimmy-model-path", placeholder="Shimmy GGUF model path (optional)")
        yield Horizontal(
            Button("Save", id="save-button"),
            Button("Save + Persist", id="save-persist-button"),
            Button("Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-button":
            self.post_message(SettingsCancelled(self))
            self.app.pop_screen()
            return

        backend = self.query_one("#backend-select", Select).value
        model = self.query_one("#gemini-model", Select).value
        api_key = self.query_one("#gemini-api-key", Input).value.strip()
        oauth_path = self.query_one("#gemini-oauth-path", Input).value.strip()
        shim_model_path = self.query_one("#shimmy-model-path", Input).value.strip()
        persist = event.button.id == "save-persist-button"

        payload = {
            "backend": backend,
            "gemini_model": model,
            "api_key": api_key,
            "oauth_creds_path": oauth_path,
            "shimmy_model_path": shim_model_path,
            "persist": persist,
        }
        self.post_message(SettingsSaved(self, payload))
        self.app.pop_screen()


class VirtuosoTUI(App):
    BINDINGS = [
        Binding("ctrl+s", "send_prompt", "Send prompt", show=False),
        Binding("ctrl+o", "open_settings", "Settings"),
        Binding("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.output_stream = TUIOutputStream(self)
        self._status_timer: Optional[Timer] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="left-pane"):
                yield Label("Prompt / Command (Ctrl+S to send, /build, /plan, /generate prefixes accepted)", id="input-label")
                yield TextArea(id="input-area", placeholder="Enter prompt or command here...", height=8)
                yield Horizontal(
                    Select(options=[("build", "Build"), ("generate", "Generate"), ("plan", "Plan")], value="build", id="action-select"),
                    Button("Send", id="send-button"),
                    Button("Settings", id="settings-button"),
                )
                yield Static("Reasoning steps", id="reasoning-title")
                yield RichLog(id="reasoning-log", highlight=True)
            with Vertical(id="right-pane"):
                yield Static("Tool Output", id="tool-title")
                yield RichLog(id="tool-log", highlight=True)
        yield Static("Status: initializing...", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._status_timer = self.set_interval(2, self.update_status)
        self.query_one("#reasoning-log", RichLog).clear()
        self.query_one("#tool-log", RichLog).clear()

    def update_status(self) -> None:
        llm_cfg = cli.config.get("llm", {})
        backend = llm_cfg.get("backend", "gemini-apikey")
        if backend == "shimmy":
            model = llm_cfg.get("shimmy", {}).get("model_path") or "local"
        else:
            model = llm_cfg.get("gemini", {}).get("model") or llm_cfg.get("gemini", {}).get("model_flash") or "gemini-2.0-flash"
        memory = "N/A"
        try:
            import psutil

            proc = psutil.Process(os.getpid())
            memory = f"{proc.memory_info().rss / 1024 / 1024:.1f}MB"
        except Exception:
            memory = "psutil not installed"
        status = f"Backend: {backend} | Model: {model} | Memory: {memory}"
        self.query_one("#status-bar", Static).update(status)

    def action_send_prompt(self) -> None:
        self._execute_prompt()

    def action_open_settings(self) -> None:
        self.push_screen(SettingsModal())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-button":
            self._execute_prompt()
        elif event.button.id == "settings-button":
            self.push_screen(SettingsModal())

    def on_settings_saved(self, event: SettingsSaved) -> None:
        payload = event.payload
        backend = payload.get("backend")
        gemini_model = payload.get("gemini_model")
        api_key = payload.get("api_key")
        oauth_creds_path = payload.get("oauth_creds_path")
        shimmy_model_path = payload.get("shimmy_model_path")
        persist = payload.get("persist", False)

        cli.config.setdefault("llm", {})
        cli.config["llm"]["backend"] = backend
        cli.config["llm"].setdefault("gemini", {})
        cli.config["llm"]["gemini"]["model"] = gemini_model
        if backend == "gemini-apikey":
            cli.config["llm"]["gemini"]["auth_method"] = "apikey"
            cli.config["llm"]["gemini"]["api_key"] = api_key
        elif backend == "gemini-oauth":
            cli.config["llm"]["gemini"]["auth_method"] = "oauth"
            cli.config["llm"]["gemini"]["oauth_creds_path"] = oauth_creds_path
        elif backend == "shimmy":
            cli.config["llm"].setdefault("shimmy", {})
            if shimmy_model_path:
                cli.config["llm"]["shimmy"]["model_path"] = shimmy_model_path

        try:
            cli.cmd_backend(
                backend,
                auth_method=cli.config["llm"]["gemini"].get("auth_method"),
                api_key=api_key,
                oauth_creds_path=oauth_creds_path,
                persist=persist,
                ask_save=False,
            )
            self.post_message(BackendChanged(self, backend, cli.config["llm"].get("gemini", {}).get("model", "")))
        except Exception as exc:
            self.query_one("#tool-log", RichLog).write(f"[red]Settings update failed: {exc}")

    def on_settings_cancelled(self, event: SettingsCancelled) -> None:
        self.query_one("#tool-log", RichLog).write("Settings update cancelled.")

    def _execute_prompt(self) -> None:
        prompt = self.query_one("#input-area", TextArea).value.strip()
        if not prompt:
            return
        action = self.query_one("#action-select", Select).value
        self.query_one("#input-area", TextArea).value = ""
        if prompt.startswith("/"):
            self.run_command(prompt)
        else:
            self.run_command(f"/{action} {prompt}")

    def run_command(self, command: str) -> None:
        self.query_one("#tool-log", RichLog).write(f"[yellow]Running: {command}")
        self.perform_command(command)

    @work
    def perform_command(self, command: str) -> None:
        with redirect_stdout(self.output_stream):
            if command.startswith("/build "):
                cli.cmd_build(command[7:].strip())
            elif command.startswith("/plan "):
                cli.cmd_plan(command[6:].strip())
            elif command.startswith("/generate "):
                cli.cmd_generate(command[10:].strip())
            elif command.startswith("/search "):
                cli.cmd_search(command[8:].strip())
            elif command.startswith("/read "):
                parts = command[6:].strip().split(maxsplit=1)
                path = parts[0] if parts else ""
                range_spec = parts[1] if len(parts) > 1 else ""
                cli.cmd_read(path, range_spec)
            elif command.startswith("/glob "):
                cli.cmd_glob(command[6:].strip())
            elif command.startswith("/status"):
                cli.cmd_status()
            elif command.startswith("/config"):
                cli.cmd_config()
            elif command.startswith("/backend "):
                cli.cmd_backend(command[9:].strip(), persist=False)
            else:
                self.output_stream.write(f"Unknown command: {command}\n")

    def on_new_log_entry(self, event: NewLogEntry) -> None:
        self.query_one("#tool-log", RichLog).write(event.text)

    def on_reasoning_step(self, event: ReasoningStep) -> None:
        self.query_one("#reasoning-log", RichLog).write(event.step)

    def on_backend_changed(self, event: BackendChanged) -> None:
        self.query_one("#status-bar", Static).update(f"Backend switched to {event.backend} | Model: {event.model}")
