# IDE Integration (VS Code, Cursor, Continue, Cline)

Virtuoso exposes an **OpenAI-compatible API** so IDE extensions can use the same backend as the CLI (Gemini or local Shimmy).

## Quick start

**Terminal 1 — start the IDE server:**

```bash
python virtuoso.py --serve
# or: dist/virtuoso.exe --serve
```

Default URL: `http://127.0.0.1:8765/v1`

**Terminal 2 — use Virtuoso CLI as usual**, or configure your IDE extension below.

## Prerequisites

1. **Cloud (recommended):** `/gemini setup` with a key from [Google AI Studio](https://aistudio.google.com/apikey). Default model: `gemini-2.5-flash`.
2. **Local:** `/profile local` then `/shimmy install` and `/shimmy start`.

## Continue.dev configuration

1. Install **Continue** in VS Code or Cursor.
2. Command palette → **Continue: Open config.yaml**.
3. Add:

```yaml
models:
  - name: Virtuoso
    provider: openai
    model: gemini-2.5-flash
    apiBase: http://127.0.0.1:8765/v1
    apiKey: dummy
```

Use the model id shown when `virtuoso --serve` starts (matches your active backend).

4. Reload the window.

## Cline / Roo Code / other OpenAI clients

Set:

- **Base URL:** `http://127.0.0.1:8765/v1`
- **API key:** `dummy` (any string)
- **Model:** value from `/status` or serve startup log

## VS Code / Cursor extension (bundled)

```bash
cd vscode-extension
# Developer: Install Extension from folder in VS Code
```

Commands:

- **Virtuoso: Open CLI** — terminal with `python virtuoso.py`
- **Virtuoso: Start IDE Server** — runs `--serve`
- **Virtuoso: Ask About Selection** — copies selection, opens CLI for `/explain`

## Profiles

| Profile | Backend | Use case |
|---------|---------|----------|
| `cloud` | Gemini API | Default, best on 8GB laptops |
| `local` | Shimmy | Offline, needs GPU/RAM |
| `offline` | Shimmy | Same as local |

```
/profile cloud
/profile local
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 502 from IDE | Run `/gemini setup` or `/shimmy start`; check `/status` |
| 429 quota | Model retired — use `gemini-2.5-flash` in config |
| Port in use | `python virtuoso.py --serve --serve-port 8766` |
| Shimmy empty/slow | Use `/profile cloud` on integrated GPUs |

## Legacy: Shimmy port 8080 directly

You can still point Continue at Shimmy's native API (`http://localhost:8080/v1`) when only using local models. The Virtuoso IDE server (`8765`) is preferred — it uses your Virtuoso config, constitution, and Gemini setup.
