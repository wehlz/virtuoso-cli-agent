# Contributing to Virtuoso CLI Agent

Thank you for contributing! This project is designed to produce both a Python package and standalone executables for users.

## Developer setup

1. Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```

2. Install dependencies:

```bash
pip install -r requirements.txt
pip install pytest pyinstaller
```

## Building the standalone executable

Use the provided script to create a standalone executable from `run_virtuoso.py`.

### Linux/macOS

```bash
bash scripts/build_standalone.sh
```

### Windows

```cmd
scripts\build_standalone.bat
```

### Icon assets

Place custom executable icons under `assets/icons/`.
- Windows: `assets/icons/virtuoso.ico`
- macOS: `assets/icons/virtuoso.icns`

If the icon file is missing, the build will still succeed without a custom icon.

To convert PNG to `.ico` or `.icns`, use tools like `ImageMagick`, `icotool`, or online converters.

### Build all supported platforms

This script runs the local platform build:

```bash
bash scripts/build_all.sh
```

> Note: Cross-platform building requires the corresponding OS environment or GitHub Actions.

### Icon assets

Place custom executable icons under `assets/icons/`:

- Windows: `assets/icons/virtuoso.ico`
- macOS: `assets/icons/virtuoso.icns`

The shell build wrappers will pass `--icon=assets/icons/virtuoso.ico` when it exists.

If you're using `assets/icons/virtuoso.png` as your source artwork, you can convert it to `.ico` and `.icns` with ImageMagick using the provided `scripts/convert_icon.sh` script.

## Packaging for PyPI

Install the package locally for development:

```bash
pip install -e .
```

Run the package entry point:

```bash
virtuoso
```

Or use the standalone launcher:

```bash
python run_virtuoso.py
```

## Testing

Run the Shimmy test suite:

```bash
python -m pytest tests/test_shimmy.py
```

Other tests:

```bash
python -m pytest tests/test_tui.py tests/test_oauth.py
```

## GitHub Actions

The `.github/workflows/build.yml` workflow builds artifacts on tag push for Windows, macOS, and Linux.
