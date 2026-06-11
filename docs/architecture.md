# Architecture

Virtuoso is intentionally small: a Python CLI, a few model backends, and lightweight local UIs around the same core commands.

## Entry Points

- `virtuoso.py` is the main CLI entry point.
- `run_virtuoso.py` is the standalone executable launcher.
- `core/web_dashboard.py` serves the browser dashboard on `127.0.0.1:8788`.
- `core/ide_server.py` serves an OpenAI-compatible local API on `127.0.0.1:8765/v1`.
- `virtuoso_tui/` contains the Textual terminal dashboard.

## Configuration

Configuration is loaded by `core/config.py`.

- Source checkouts use `virtuoso.yaml` in the project root.
- Installed package usage creates `virtuoso.yaml` in the current working directory when missing.
- Frozen executables use config beside the executable.

The default backend is `gemini-apikey` because it works well on low-memory laptops.

## Model Backends

`core/llm_client.py` chooses the backend:

- Gemini API key and OAuth clients live in `core/gemini_client.py`.
- OpenAI-compatible providers use `core/openai_compat_client.py`.
- Local Shimmy support uses `core/shimmy_client.py` and `core/shimmy_manager.py`.

All backends expose a streaming `generate()` interface.

## Agent Flow

High-level build behavior is coordinated by `core/agents.py`:

1. Plan the task.
2. Generate code.
3. Review output.
4. Try debug repair when possible.
5. Save generated code through `core/output_paths.py` when requested.

## Dashboard Flow

The browser dashboard is a small local HTTP app:

- Static HTML lives in `virtuoso_web/dashboard.html`.
- API routes are implemented in `core/web_dashboard.py`.
- Long-running generate/build calls run behind a lock so requests do not overlap.

## Packaging

- `MANIFEST.in` controls source distribution contents.
- `setup.py` includes package data for wheel installs.
- `scripts/build_standalone.py` builds a PyInstaller executable and bundles config, dashboard assets, TUI, and icons.
