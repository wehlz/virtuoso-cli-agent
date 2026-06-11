# Demo Script

Use this outline to record a 30-60 second GIF or video for the README.

## Automated README GIF

The committed README GIF is generated from the real dashboard UI with browser
automation. It stubs the API responses during recording, so it is repeatable and
does not require a real API key.

```bash
pip install -e ".[dev]"
python -m playwright install chromium
python scripts/record_dashboard_demo.py
```

The script writes `docs/assets/dashboard-demo.gif`. For troubleshooting, keep
the source PNG frames:

```bash
python scripts/record_dashboard_demo.py --keep-frames
```

## Setup

1. Start from a clean terminal in the project root.
2. Run:

   ```bash
   python virtuoso.py --dashboard
   ```

3. Open `http://127.0.0.1:8788`.
4. Paste a Gemini API key in the setup panel.

## Recording Flow

1. Show the dashboard status changing to connected.
2. Select **Build**.
3. Enter:

   ```text
   make a Python todo app on my desktop titled todo
   ```

4. Click **Run**.
5. Show the generated output.
6. Show the saved file path.
7. Open the saved file in an editor.

## Optional Second Clip

1. Start the IDE server:

   ```bash
   python virtuoso.py --serve
   ```

2. Show Continue/Cursor using `http://127.0.0.1:8765/v1`.

## Suggested Caption

Virtuoso running on a normal laptop: browser dashboard, Gemini setup, build prompt, generated code, and saved file output.
