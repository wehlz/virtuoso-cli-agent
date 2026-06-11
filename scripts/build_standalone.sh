#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
# Build the standalone executable and use the custom icon if assets/icons/virtuoso.ico or asset/icons/virtuoso.ico exists.
ICON_ARG=""
if [ -f assets/icons/virtuoso.ico ]; then
  ICON_ARG="--icon=assets/icons/virtuoso.ico"
elif [ -f asset/icons/virtuoso.ico ]; then
  ICON_ARG="--icon=asset/icons/virtuoso.ico"
fi
python scripts/build_standalone.py $ICON_ARG
