"""Browser dashboard for Virtuoso (chat, build, plan without raw console)."""

from __future__ import annotations

import io
import json
import mimetypes
import os
import platform
import subprocess
import sys
import threading
import webbrowser
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

import virtuoso as cli
from core.gemini_models import DEFAULT_GEMINI_FLASH, resolve_gemini_model_from_config
from core.gemini_setup import ensure_gemini_configured, has_gemini_api_key
from core.openai_compat_client import resolve_openai_api_key

DASHBOARD_VERSION = "2.2"

_cancel_event = threading.Event()
_job_lock = threading.Lock()


def _dashboard_html_path() -> Optional[Path]:
    from core.paths import app_dir, is_frozen, resource_dir

    candidates = [
        resource_dir() / "virtuoso_web" / "dashboard.html",
        Path(__file__).resolve().parent.parent / "virtuoso_web" / "dashboard.html",
    ]
    if is_frozen():
        candidates.append(app_dir() / "virtuoso_web" / "dashboard.html")
    for path in candidates:
        if path.is_file():
            return path
    return None


def _logo_path() -> Optional[Path]:
    from core.paths import app_dir, is_frozen, resource_dir

    names = ("virtuoso.ico", "virtuoso.png")
    bases = [resource_dir(), Path(__file__).resolve().parent.parent]
    if is_frozen():
        bases.append(app_dir())
    for base in bases:
        for name in names:
            candidate = base / "assets" / "icons" / name
            if candidate.is_file():
                return candidate
    return None


def _load_dashboard_html() -> str:
    path = _dashboard_html_path()
    if path:
        return path.read_text(encoding="utf-8")
    return "<html><body><h1>Virtuoso</h1><p>Dashboard assets missing.</p></body></html>"


def _open_browser(url: str) -> None:
    opened = False
    if platform.system() == "Windows":
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            opened = True
        except OSError:
            try:
                subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
                opened = True
            except OSError:
                pass
    if not opened:
        try:
            opened = webbrowser.open(url, new=1)
        except Exception:
            pass
    if not opened:
        print(f"Could not open browser automatically. Copy this URL: {url}")


def _print_banner(url: str, port: int) -> None:
    line = "=" * 56
    print(line)
    print("  VIRTUOSO DASHBOARD IS RUNNING")
    print(f"  Open in your browser:  {url}")
    print(f"  Port: {port}  |  Dashboard v{DASHBOARD_VERSION}")
    print(f"  Connected: {'yes' if cli.llm_client else 'no — use Setup box in browser'}")
    print("  Keep this window open while using the UI")
    print(line)
    sys.stdout.flush()


def _status_payload() -> Dict[str, Any]:
    config = cli.config or {}
    llm = config.get("llm", {})
    backend = llm.get("backend", "gemini-apikey")
    profile = config.get("cli", {}).get("active_profile", "cloud")
    model = DEFAULT_GEMINI_FLASH
    api_key_present = False

    if backend == "shimmy":
        model = llm.get("shimmy", {}).get("model_path") or "shimmy-local"
    elif backend == "openai":
        oai = llm.get("openai", {})
        model = oai.get("model", "gpt-4o-mini")
        api_key_present = resolve_openai_api_key(oai) is not None
    elif backend.startswith("gemini"):
        model = resolve_gemini_model_from_config(llm.get("gemini", {}), backend)
        api_key_present = has_gemini_api_key(config)

    connected = cli.llm_client is not None and (
        backend == "shimmy" or api_key_present or backend == "gemini-oauth"
    )

    return {
        "connected": connected,
        "backend": backend,
        "model": model,
        "profile": profile,
        "api_key_present": api_key_present,
        "dashboard_version": DASHBOARD_VERSION,
        "busy": _job_lock.locked(),
    }


def _setup_backend(provider: str, api_key: str) -> Dict[str, Any]:
    api_key = (api_key or "").strip()
    if not api_key:
        return {"error": "API key cannot be empty."}
    try:
        if provider == "openai":
            from core.openai_setup import apply_provider_preset

            apply_provider_preset("openrouter", api_key)
        else:
            from core.gemini_setup import save_gemini_api_key

            save_gemini_api_key(api_key)
        cli._reconnect_llm()
        return {"ok": True, "connected": cli.llm_client is not None}
    except Exception as exc:
        return {"error": str(exc)}


def request_cancel() -> None:
    _cancel_event.set()


def _run_action(mode: str, prompt: str) -> Dict[str, Any]:
    if cli.llm_client is None:
        cli._reconnect_llm()
    if cli.llm_client is None:
        return {
            "error": (
                "Backend not connected. Paste your Gemini API key in the Setup panel, "
                "then click Save & Connect."
            )
        }

    _cancel_event.clear()
    buffer = io.StringIO()
    saved_path: Optional[str] = None
    cancel_check = lambda: _cancel_event.is_set()

    with redirect_stdout(buffer):
        if _cancel_event.is_set():
            return {"error": "Cancelled by user", "cancelled": True}
        if mode == "chat":
            if cancel_check():
                return {"error": "Cancelled by user", "cancelled": True}
            cli.cmd_generate(prompt)
        elif mode == "build":
            cli.cmd_build(prompt, cancel_check=cancel_check)
        elif mode == "plan":
            if cancel_check():
                return {"error": "Cancelled by user", "cancelled": True}
            cli.cmd_plan(prompt)
        elif mode in ("fix", "explain", "test", "refactor", "review"):
            if cancel_check():
                return {"error": "Cancelled by user", "cancelled": True}
            cli.cmd_generate(prompt, preset=mode)
        else:
            return {"error": f"Unknown mode: {mode}"}

    if cancel_check():
        partial = buffer.getvalue().strip() or (cli.last_code if mode == "build" else "")
        result: Dict[str, Any] = {"text": partial or "Cancelled by user.", "cancelled": True}
        return result

    output = buffer.getvalue().strip()
    if output:
        text = output
    elif mode == "build" and cli.last_code:
        text = cli.last_code
    else:
        text = "(No output)"

    if mode == "build" and "💾 Saved to:" in text:
        for line in text.splitlines():
            if "💾 Saved to:" in line:
                saved_path = line.split("💾 Saved to:", 1)[-1].strip()
                break

    result = {"text": text}
    if saved_path:
        result["saved_path"] = saved_path
    return result


def make_handler() -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        server_version = "VirtuosoDashboard/2.2"

        def log_message(self, format: str, *args) -> None:
            return

        def _send_json(self, code: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_bytes(self, code: int, body: bytes, content_type: str, extra_headers: Optional[Dict[str, str]] = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if extra_headers:
                for key, value in extra_headers.items():
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw.decode("utf-8"))

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                body = _load_dashboard_html().encode("utf-8")
                self._send_bytes(
                    200,
                    body,
                    "text/html; charset=utf-8",
                    {
                        "Cache-Control": "no-store, no-cache, must-revalidate",
                        "X-Virtuoso-Dashboard": DASHBOARD_VERSION,
                    },
                )
                return
            if path in ("/assets/logo.ico", "/assets/logo.png", "/favicon.ico"):
                logo = _logo_path()
                if logo:
                    data = logo.read_bytes()
                    mime = mimetypes.guess_type(logo.name)[0] or "image/x-icon"
                    self._send_bytes(200, data, mime, {"Cache-Control": "public, max-age=3600"})
                    return
                self._send_json(404, {"error": "Logo not found"})
                return
            if path == "/api/version":
                self._send_json(200, {"version": DASHBOARD_VERSION})
                return
            if path == "/api/status":
                self._send_json(200, _status_payload())
                return
            self._send_json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            try:
                data = self._read_json() if self.headers.get("Content-Length") else {}
                if path == "/api/cancel":
                    request_cancel()
                    self._send_json(200, {"ok": True, "cancelled": True})
                    return
                if path == "/api/setup":
                    provider = (data.get("provider") or "gemini").strip().lower()
                    result = _setup_backend(provider, data.get("api_key") or "")
                    code = 200 if result.get("ok") else 400
                    self._send_json(code, result)
                    return
                if path != "/api/generate":
                    self._send_json(404, {"error": "Not found"})
                    return
                prompt = (data.get("prompt") or "").strip()
                mode = (data.get("mode") or "chat").strip().lower()
                if not prompt:
                    self._send_json(400, {"error": "Prompt is required"})
                    return
                with _job_lock:
                    result = _run_action(mode, prompt)
                _cancel_event.clear()
                if "error" in result and not result.get("cancelled"):
                    self._send_json(503, result)
                    return
                self._send_json(200, result)
            except Exception as exc:
                if _job_lock.locked():
                    _job_lock.release()
                self._send_json(500, {"error": str(exc)})

    return DashboardHandler


class DashboardHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False


def _bind_httpd(host: str, port: int, handler: type[BaseHTTPRequestHandler]) -> tuple[DashboardHTTPServer, int]:
    last_error: Optional[Exception] = None
    for offset in range(10):
        candidate = port + offset
        try:
            httpd = DashboardHTTPServer((host, candidate), handler)
            return httpd, candidate
        except OSError as exc:
            last_error = exc
    raise RuntimeError(f"Could not bind dashboard on ports {port}-{port + 9}: {last_error}")


def _bootstrap_backend() -> None:
    ensure_gemini_configured()
    if not cli.config:
        cli.init()
    elif cli.llm_client is None:
        cli.init()
    if cli.llm_client is None:
        cli._reconnect_llm()


def run_dashboard(host: str = "127.0.0.1", port: int = 8788, open_browser: bool = True) -> None:
    _bootstrap_backend()
    handler = make_handler()
    httpd, port = _bind_httpd(host, port, handler)
    url = f"http://{host}:{port}/"
    _print_banner(url, port)

    if open_browser:
        threading.Timer(0.5, lambda: _open_browser(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        httpd.server_close()
