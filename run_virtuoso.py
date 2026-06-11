import os
import platform
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message=".*doesn't match a supported version.*")

from core.paths import app_dir, is_frozen, shimmy_dir

DEFAULT_PORT = 8080


def _binary_name() -> str:
    return "shimmy.exe" if platform.system() == "Windows" else "shimmy"


def _shimmy_binary() -> Path:
    return shimmy_dir() / _binary_name()


def _install_shimmy() -> Path:
    from core.shimmy_manager import install_shimmy

    return install_shimmy()


def _ensure_model() -> Path:
    from core.model_manager import ensure_default_model

    return ensure_default_model()


def _start_shimmy() -> bool:
    """Start Shimmy if needed. Returns True when this launcher started it."""
    from core.config import load_config
    from core.shimmy_manager import is_shimmy_running, start_shimmy

    config = load_config()
    backend = config.get("llm", {}).get("backend", "")
    if backend not in ("shimmy",):
        return False

    port = config.get("llm", {}).get("shimmy", {}).get("port", DEFAULT_PORT)
    if is_shimmy_running(port):
        print(f"Shimmy already running on port {port}.")
        return False

    binary = _shimmy_binary()
    if not binary.exists():
        print("Shimmy binary not found locally. Downloading into virtuoso_data/shimmy...")
        binary = _install_shimmy()

    model_path = _ensure_model()
    print(f"Using model: {model_path}")

    shim_cfg = dict(config.get("llm", {}).get("shimmy", {}))
    shim_cfg["binary_path"] = str(binary)
    shim_cfg.setdefault("model_path", str(model_path))
    shim_cfg.setdefault("auto_download_model", False)

    print(f"Starting Shimmy from {binary}...")
    start_shimmy(
        port=shim_cfg.get("port", DEFAULT_PORT),
        model=shim_cfg.get("model", "auto"),
        binary_path=str(binary),
        config=shim_cfg,
    )
    return True


def _stop_shimmy_quiet():
    from core.shimmy_manager import stop_shimmy_quiet

    stop_shimmy_quiet()


def main() -> int:
    if is_frozen():
        os.chdir(app_dir())

    started_shimmy = False
    exit_code = 0
    try:
        from core.config import load_config

        if load_config().get("llm", {}).get("backend") == "shimmy":
            try:
                started_shimmy = _start_shimmy()
            except Exception as exc:
                print(f"Warning: Shimmy could not be started: {exc}")
                print("Tip: use /profile cloud and /gemini setup for Gemini on 8GB laptops.")

        import virtuoso

        # Double-clicking the .exe opens the browser dashboard by default.
        if len(sys.argv) == 1 and is_frozen():
            sys.argv.append("--dashboard")

        if "--serve" in sys.argv:
            args = virtuoso.parse_args()
            virtuoso.cmd_serve(host=args.serve_host, port=args.serve_port)
        elif "--dashboard" in sys.argv:
            args = virtuoso.parse_args()
            virtuoso.cmd_dashboard(host=args.dashboard_host, port=args.dashboard_port)
        elif "--tui" in sys.argv:
            try:
                virtuoso.run_tui()
            except Exception as exc:
                print(f"TUI unavailable ({exc}). Falling back to CLI.")
                virtuoso.main()
        else:
            virtuoso.main()
    except KeyboardInterrupt:
        print("\nExiting.")
    except Exception as exc:
        print(f"Failed to start Virtuoso: {exc}")
        exit_code = 1
        if is_frozen():
            try:
                input("\nPress Enter to close...")
            except (EOFError, KeyboardInterrupt):
                pass
    finally:
        if started_shimmy:
            _stop_shimmy_quiet()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
