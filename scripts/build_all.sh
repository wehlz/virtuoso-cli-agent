#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

ICON_ARG=""
if [ -f assets/icons/virtuoso.ico ]; then
  ICON_ARG="--icon=assets/icons/virtuoso.ico"
elif [ -f asset/icons/virtuoso.ico ]; then
  ICON_ARG="--icon=asset/icons/virtuoso.ico"
fi

OS_NAME="$(uname -s)"
case "$OS_NAME" in
  Linux)
    echo "Building for Linux..."
    python scripts/build_standalone.py $ICON_ARG
    ;;
  Darwin)
    echo "Building for macOS..."
    python scripts/build_standalone.py $ICON_ARG
    ;;
  CYGWIN*|MINGW*|MSYS*)
    echo "Building for Windows..."
    python scripts/build_standalone.py $ICON_ARG
    ;;
  *)
    echo "Unsupported platform: $OS_NAME"
    exit 1
    ;;
esac

echo "Standalone build complete. Check dist/ for artifacts."
