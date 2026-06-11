import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from core.model_manager import ensure_default_model, locate_model
from core.paths import shimmy_dir

DEFAULT_PORT = 8080
DEFAULT_MODEL = "auto"

_SHIMMY_PROCESS: Optional[subprocess.Popen] = None


def _binary_name() -> str:
    return "shimmy.exe" if platform.system() == "Windows" else "shimmy"


def find_shimmy_binary(binary_path: Optional[str] = None) -> Optional[Path]:
    """Search for the Shimmy binary in config, virtuoso_data, ./bin/, and PATH."""
    if binary_path:
        candidate = Path(binary_path).expanduser()
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    candidate = shimmy_dir() / _binary_name()
    if candidate.exists() and candidate.is_file():
        return candidate.resolve()

    candidate = Path.cwd() / "bin" / _binary_name()
    if candidate.exists() and candidate.is_file():
        return candidate.resolve()

    path = shutil.which(_binary_name())
    if path:
        return Path(path)

    return None


def resolve_shimmy_model(
    port: int = DEFAULT_PORT,
    configured: str = "",
    preferred_path: Optional[str] = None,
) -> str:
    """Return the configured model or auto-detect from Shimmy's /v1/models list."""
    if configured and configured not in ("auto", ""):
        return configured

    preferred_stem = Path(preferred_path).stem if preferred_path else None
    preferred_lower = preferred_stem.lower() if preferred_stem else None

    try:
        response = requests.get(f"http://127.0.0.1:{port}/v1/models", timeout=2)
        if response.status_code == 200:
            models = response.json().get("data", [])
            ids = [m["id"] for m in models if m.get("id")]
            if preferred_lower and ids:
                for model_id in ids:
                    if model_id.lower() == preferred_lower:
                        return model_id
                for model_id in ids:
                    if preferred_lower in model_id.lower():
                        return model_id
            if ids and not preferred_lower:
                return ids[0]
    except Exception:
        pass

    if preferred_lower:
        return preferred_lower
    return configured or DEFAULT_MODEL


def is_shimmy_healthy(port: int = DEFAULT_PORT, timeout: float = 2.0) -> bool:
    try:
        response = requests.get(f"http://127.0.0.1:{port}/health", timeout=timeout)
        if response.status_code == 200:
            payload = response.json()
            return payload.get("status") == "ok"
    except Exception:
        pass
    return False


def is_shimmy_running(port: int = DEFAULT_PORT, timeout: float = 2.0) -> bool:
    """Return True if Shimmy responds on the OpenAI-compatible models endpoint."""
    try:
        response = requests.get(f"http://127.0.0.1:{port}/v1/models", timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


def _resolve_model_path(config: Dict[str, Any]) -> Optional[Path]:
    configured = config.get("model_path")
    found = locate_model(configured)
    if found:
        return found

    if config.get("auto_download_model", True):
        try:
            return ensure_default_model()
        except Exception as exc:
            raise RuntimeError(
                f"Could not locate a GGUF model and automatic download failed: {exc}"
            ) from exc
    return None


def _build_command(binary_path: Path, port: int, config: Dict[str, Any]) -> list[str]:
    command = [str(binary_path), "serve", "--bind", f"127.0.0.1:{port}"]

    model_path = _resolve_model_path(config)
    if model_path:
        command.extend(["--model-path", str(model_path)])

    extra_args: List[str] = list(config.get("extra_args") or [])
    if not extra_args:
        extra_args = ["--kv-quant", "int4", "--ctx", "1024", "--prefill-chunk", "8"]
    command.extend(extra_args)
    return command


def start_shimmy(
    port: int = DEFAULT_PORT,
    model: str = DEFAULT_MODEL,
    binary_path: Optional[str] = None,
    timeout: float = 60.0,
    config: Optional[Dict[str, Any]] = None,
) -> subprocess.Popen:
    """Start a Shimmy subprocess and wait for it to become ready."""
    global _SHIMMY_PROCESS
    if is_shimmy_running(port):
        return _SHIMMY_PROCESS

    shim_cfg = dict(config or {})
    shim_cfg.setdefault("port", port)
    shim_cfg.setdefault("model", model)

    shimmy_binary = find_shimmy_binary(binary_path or shim_cfg.get("binary_path"))
    if shimmy_binary is None:
        raise RuntimeError(
            "Shimmy binary not found. Run /shimmy install or place shimmy in virtuoso_data/shimmy/."
        )

    command = _build_command(shimmy_binary, port, shim_cfg)
    try:
        _SHIMMY_PROCESS = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to launch Shimmy: {exc}") from exc

    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_shimmy_running(port):
            return _SHIMMY_PROCESS
        if _SHIMMY_PROCESS.poll() is not None:
            raise RuntimeError(
                "Shimmy exited immediately. Your GPU may not support the configured model. "
                "Try a smaller GGUF quant or set llm.shimmy.model_path in virtuoso.yaml."
            )
        time.sleep(0.5)

    raise RuntimeError(f"Shimmy did not become ready on port {port} within {timeout} seconds.")


def stop_shimmy() -> None:
    """Stop the Shimmy subprocess if it was started by this process."""
    global _SHIMMY_PROCESS
    if _SHIMMY_PROCESS is not None and _SHIMMY_PROCESS.poll() is None:
        _SHIMMY_PROCESS.terminate()
        try:
            _SHIMMY_PROCESS.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _SHIMMY_PROCESS.kill()
        _SHIMMY_PROCESS = None
        return

    raise RuntimeError(
        "Shimmy process is not managed by this Virtuoso instance or is not running."
    )


def stop_shimmy_quiet() -> None:
    """Stop managed Shimmy without raising if not managed."""
    try:
        stop_shimmy()
    except Exception:
        pass


def ensure_shimmy_running(config: Dict[str, Any]) -> None:
    """Ensure Shimmy is running according to the provided configuration."""
    port = config.get("port", DEFAULT_PORT)
    model = config.get("model", DEFAULT_MODEL)
    binary_path = config.get("binary_path")
    enabled = config.get("enabled", True)
    auto_start = config.get("auto_start", True)

    if not enabled:
        raise RuntimeError("Shimmy is disabled in configuration.")

    if is_shimmy_running(port):
        return

    if not auto_start:
        raise RuntimeError(
            f"Shimmy is not running on port {port} and auto_start is disabled."
        )

    start_shimmy(port=port, model=model, binary_path=binary_path, config=config)


def install_shimmy(binary_path: Optional[Path] = None, force: bool = False) -> Path:
    """Download Shimmy into virtuoso_data/shimmy."""
    from scripts.download_shimmy import install_shimmy as _install

    target = binary_path or shimmy_dir()
    target.mkdir(parents=True, exist_ok=True)
    return _install(target, force=force)


def install_shimmy_help() -> str:
    return (
        "Shimmy is a lightweight local OpenAI-compatible server.\n"
        "Virtuoso can auto-download Shimmy and a ~1 GB coder model into virtuoso_data/.\n"
        "Manual install:\n"
        "  cargo install shimmy\n"
        "or download a pre-built binary from:\n"
        "  https://github.com/Michael-A-Kuykendall/shimmy/releases\n"
        "On Windows, use the .exe binary or run /shimmy install.\n"
        "Then run /shimmy start or configure llm.backend: \"shimmy\"."
    )
