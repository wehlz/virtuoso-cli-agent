"""OpenAI-compatible HTTP API for IDE extensions (Continue, Cline, etc.)."""

from __future__ import annotations

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.config import load_config
from core.conversation import build_conversation_prompt, max_conversation_exchanges
from core.gemini_models import resolve_gemini_model_from_config
from core.llm_client import get_llm_client
from core.shimmy_manager import resolve_shimmy_model


class IdeServerState:
    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.llm_client = None
        self.conversation_history: List[Dict[str, str]] = []
        self.model_id = "virtuoso"
        self.lock = threading.Lock()

    def initialize(self) -> None:
        self.config = load_config()
        llm_cfg = dict(self.config.get("llm", {}))
        self.llm_client = get_llm_client(llm_cfg)
        backend = llm_cfg.get("backend", "gemini-apikey")
        if backend == "shimmy":
            shim = llm_cfg.get("shimmy", {})
            self.model_id = resolve_shimmy_model(
                port=shim.get("port", 8080),
                configured=shim.get("model", "auto"),
                preferred_path=shim.get("model_path"),
            )
        elif backend.startswith("gemini"):
            self.model_id = resolve_gemini_model_from_config(llm_cfg.get("gemini", {}), backend)
        else:
            self.model_id = "virtuoso"

    def models_payload(self) -> Dict[str, Any]:
        return {
            "object": "list",
            "data": [
                {
                    "id": self.model_id,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "virtuoso",
                }
            ],
        }


def _message_content(message: Dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
        return "\n".join(texts)
    return str(content)


def parse_chat_messages(messages: List[Dict[str, Any]]) -> Tuple[str, Optional[str]]:
    """Convert OpenAI messages to (prompt, system_prompt)."""
    system_parts: List[str] = []
    turns: List[Dict[str, str]] = []
    for message in messages:
        role = message.get("role", "user")
        text = _message_content(message).strip()
        if not text:
            continue
        if role == "system":
            system_parts.append(text)
        elif role in ("user", "assistant"):
            turns.append({"role": role, "content": text})

    if not turns:
        return "", "\n\n".join(system_parts) if system_parts else None

    last = turns[-1]
    if last["role"] != "user":
        prompt = "\n".join(f"{t['role']}: {t['content']}" for t in turns)
        return prompt, "\n\n".join(system_parts) if system_parts else None

    history = turns[:-1]
    user_input = last["content"]
    if history:
        hist_dicts = []
        for item in history:
            hist_dicts.append({"role": item["role"], "content": item["content"]})
        prompt = build_conversation_prompt(user_input, hist_dicts, max_exchanges=10)
    else:
        prompt = user_input

    system_prompt = "\n\n".join(system_parts) if system_parts else None
    return prompt, system_prompt


def _chunk_sse(model: str, text: str, finish: bool = False) -> str:
    payload = {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {} if finish else {"content": text},
                "finish_reason": "stop" if finish else None,
            }
        ],
    }
    return f"data: {json.dumps(payload)}\n\n"


def _completion_json(model: str, text: str) -> Dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def make_handler(state: IdeServerState) -> type[BaseHTTPRequestHandler]:
    class IdeAPIHandler(BaseHTTPRequestHandler):
        server_version = "VirtuosoIDE/1.0"

        def log_message(self, fmt: str, *args) -> None:
            return

        def _read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw.decode("utf-8") or "{}")

        def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_sse(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

        def do_GET(self) -> None:
            if self.path in ("/v1/models", "/v1/models/"):
                self._send_json(200, state.models_payload())
                return
            if self.path in ("/health", "/health/"):
                self._send_json(200, {"status": "ok", "model": state.model_id})
                return
            self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path not in ("/v1/chat/completions", "/v1/chat/completions/"):
                self._send_json(404, {"error": "not found"})
                return

            if state.llm_client is None:
                self._send_json(503, {"error": "LLM backend not initialized. Run /gemini setup or /backend shimmy."})
                return

            try:
                body = self._read_json()
            except json.JSONDecodeError:
                self._send_json(400, {"error": "invalid json"})
                return

            messages = body.get("messages") or []
            stream = bool(body.get("stream", False))
            prompt, system_prompt = parse_chat_messages(messages)
            if not prompt:
                self._send_json(400, {"error": "no user message in request"})
                return

            model = body.get("model") or state.model_id

            try:
                if stream:
                    self._send_sse()
                    full = []
                    for chunk in state.llm_client.generate(prompt, system_prompt=system_prompt):
                        full.append(chunk)
                        self.wfile.write(_chunk_sse(model, chunk).encode("utf-8"))
                        self.wfile.flush()
                    self.wfile.write(_chunk_sse(model, "", finish=True).encode("utf-8"))
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                    with state.lock:
                        if full:
                            last_user = messages[-1] if messages else {}
                            if last_user.get("role") == "user":
                                state.conversation_history.append(
                                    {"role": "user", "content": _message_content(last_user)}
                                )
                                state.conversation_history.append(
                                    {"role": "assistant", "content": "".join(full)}
                                )
                    return

                full_text = "".join(
                    state.llm_client.generate(prompt, system_prompt=system_prompt)
                )
                self._send_json(200, _completion_json(model, full_text))
            except Exception as exc:
                self._send_json(502, {"error": {"message": str(exc), "type": "server_error"}})

    return IdeAPIHandler


def run_ide_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    state = IdeServerState()
    try:
        state.initialize()
    except Exception as exc:
        print(f"Warning: LLM backend not ready ({exc}).")
        print("Server will start; configure with /gemini setup or /profile local, then restart --serve.")
    handler = make_handler(state)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"Virtuoso IDE server listening on http://{host}:{port}/v1")
    print(f"Model: {state.model_id}")
    print("Configure Continue/Cline with apiBase: http://127.0.0.1:{port}/v1  apiKey: dummy")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down IDE server.")
        httpd.shutdown()
