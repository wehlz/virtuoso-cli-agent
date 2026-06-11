# Standalone Executable Usage

Virtuoso can be distributed as a standalone executable that bundles the Python runtime, your code, and a local Shimmy launcher.

## Downloading the standalone version

Place the executable for your platform in a convenient directory.

- Windows: `virtuoso.exe`
- macOS: `virtuoso`
- Linux: `virtuoso`

## First run

On first execution, the standalone launcher will:

1. Create `virtuoso_data/shimmy` next to the executable.
2. Download the Shimmy binary for your OS if it is not already present.
3. Start Shimmy as a background subprocess.
4. Launch the Textual dashboard if available.

If the TUI cannot start, the launcher falls back to the CLI.

## Running

From a terminal:

```bash
./virtuoso
```

On Windows:

```powershell
.\virtuoso.exe
```

If you prefer the CLI only, run the installed Python version:

```bash
python run_virtuoso.py
```

## Data location

The standalone launcher stores Shimmy and support files under:

- `virtuoso_data/shimmy/`

This keeps the executable portable and self-contained.

## Troubleshooting

### Shimmy download failed

- Ensure your system has internet access.
- If the automatic download fails, install Shimmy manually and place the binary in `virtuoso_data/shimmy/`.
- On Windows, the binary should be named `shimmy.exe`.
- On macOS/Linux, it should be named `shimmy` and have execute permissions.

### Terminal windows on Windows

The first version of the standalone launcher keeps the terminal visible by default. This is intentional for debugging and automatic startup.

### Use the latest config

If you need to change the Shimmy port, update `virtuoso.yaml`:

```yaml
llm:
  backend: "shimmy"
  shimmy:
    port: 8080
```
