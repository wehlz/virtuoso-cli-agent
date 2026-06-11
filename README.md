# Virtuoso CLI Agent

Lightweight coding agent for **8GB laptops**: chat in the terminal, plan/build code, and plug into **VS Code / Cursor** via an OpenAI-compatible API.

## Features

- **Gemini (default)** — cloud inference with `/gemini setup` and multi-turn chat
- **OpenAI-compatible APIs** — OpenRouter, Groq, Together, OpenAI via `/openai setup`
- **Shimmy (optional)** — local offline models via `/profile local`
- **File output** — `/build` saves to Desktop when you say "on my desktop titled …"
- **IDE server** — `python virtuoso.py --serve` for Continue, Cline, etc.
- **Agent tools** — `/plan`, `/build`, `/search`, `/read`, sandboxed `/run`
- **Presets** — `/fix`, `/explain`, `/test`, `/refactor`, `/review`
- **Standalone exe** — `dist/virtuoso.exe` (Windows)

## Quick start

```bash
pip install -r requirements.txt
cp virtuoso.yaml.example virtuoso.yaml   # Windows: copy virtuoso.yaml.example virtuoso.yaml
python virtuoso.py
```

### Browser dashboard (recommended UI)

```bash
python virtuoso.py --dashboard
```

Opens **http://127.0.0.1:8788** in your browser — chat, build, plan, and presets without typing in the raw console.

Windows shortcut: double-click `start_dashboard.bat` in the project root (or `dist\virtuoso.exe` after building).

Other UIs:

| UI | Command | Best for |
|----|---------|----------|
| **Browser dashboard** | `python virtuoso.py --dashboard` | Chat + build + save files |
| Terminal dashboard | `python virtuoso.py --tui` | Keyboard-only terminal UI |
| Cursor / VS Code | `python virtuoso.py --serve` + Continue | Coding inside your editor |

First launch runs a short wizard. Then:

```
/gemini setup          # paste API key from https://aistudio.google.com/apikey
hello                  # chat directly at >
/status
```

### Profiles

```
/profile cloud    # Gemini (default)
/profile local    # Shimmy — then /shimmy install && /shimmy start
```

### Alternative to Google (API key)

```
/openai setup          # wizard: OpenRouter, Groq, Together, or OpenAI
/openai openrouter     # quick setup for OpenRouter (free models available)
/backend openai        # switch after setup
```

Popular options:

| Provider | Get key | Notes |
|----------|---------|-------|
| [OpenRouter](https://openrouter.ai/keys) | Free tier models | Easiest Gemini alternative |
| [Groq](https://console.groq.com/keys) | Fast inference | Good for chat |
| [OpenAI](https://platform.openai.com/api-keys) | Paid | `gpt-4o-mini` default |
| Shimmy (local) | No key | `/profile local` — needs GPU/RAM |

### Save files from `/build`

```
/build a python fraction solver on my desktop titled ai test math
/build --save C:\Users\you\Desktop\script.py my goal here
/save C:\Users\you\Desktop\script.py    # save last build output manually
```

### IDE integration

```bash
python virtuoso.py --serve
```

Point Continue at `http://127.0.0.1:8765/v1` — see [docs/continue_integration.md](docs/continue_integration.md).

## Commands

| Command | Description |
|---------|-------------|
| `> your question` | Chat (with memory) |
| `/gemini setup` | Configure API key |
| `/profile cloud\|local` | Switch cloud vs local |
| `/serve` | Start IDE API (or use `--serve` flag) |
| `/plan`, `/build` | Reasoning and multi-agent codegen |
| `/fix`, `/explain`, `/test` | Preset prompts |
| `/shimmy start` | Local model server |
| `/backend shimmy` | Switch backend at runtime |
| `/clear` | Reset conversation |
| `/status` | Backend health |
| `/exit` | Quit |

## Configuration

Copy the template if you have not already:

```bash
cp virtuoso.yaml.example virtuoso.yaml
```

Edit `virtuoso.yaml` (this file is gitignored — never commit API keys):

```yaml
llm:
  backend: gemini-apikey
  gemini:
    model: gemini-2.5-flash
    api_key: ""   # or use GEMINI_API_KEY env var
  shimmy:
    model_path: virtuoso_data/models/Qwen2.5-Coder-0.5B-Instruct-Q4_K_M.gguf
sandbox:
  enabled: true
cli:
  active_profile: cloud
  ide_server_port: 8765
```

## Standalone executable

```bash
python scripts/build_standalone.py
# Output: dist/virtuoso.exe (bundles virtuoso.yaml.example with empty keys)
```

On first run beside the exe, config is copied to `virtuoso.yaml` next to the executable — add your API key there or use `/gemini setup`.

Place `virtuoso_data/` beside the exe for Shimmy and local models.

## VS Code extension

Load `vscode-extension/` as an unpacked extension for commands to open the CLI and IDE server.

## Hardware guide

| Machine | Recommended |
|---------|-------------|
| 8GB laptop, integrated GPU | **Gemini** (`/profile cloud`) |
| Discrete GPU / 16GB+ RAM | Gemini or **Shimmy** local |
| Offline only | `/profile local` + 0.5B model |

## SWE-bench (optional — not for 8GB laptops)

Benchmark scripts under `scripts/` need **Docker**, **16+ GB RAM**, and large disk. They are not required for normal use. On an 8GB machine the runner exits with a clear message; use Virtuoso via Gemini instead.

## Development

```bash
python -m pytest tests/ -q --ignore=tests/test_tui.py --ignore=tests/test_gemini_integration.py
```

## Privacy

- **Gemini** sends prompts to Google.
- **Shimmy** runs entirely on your machine.

## License

[MIT](LICENSE)
