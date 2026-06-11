# Virtuoso VS Code / Cursor Extension

Thin helper extension (not published to marketplace).

## Install (developer mode)

1. Open VS Code or Cursor.
2. Extensions → `...` → **Install from VSIX** or **Load Extension** from folder.
3. Select this `vscode-extension` directory.

## Commands

- **Virtuoso: Open CLI** — opens a terminal running `python virtuoso.py`
- **Virtuoso: Start IDE Server** — runs `python virtuoso.py --serve`
- **Virtuoso: Ask About Selection** — copies selection to clipboard and opens CLI; type `/explain` and paste

Ensure `python` and Virtuoso are on PATH, or run from the project root.
