#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

DEFAULT_SRC="assets/icons/virtuoso.png"
ALT_SRC="asset/icons/virtuoso.png"
SRC=${1:-$DEFAULT_SRC}
if [ ! -f "$SRC" ]; then
  if [ -f "$ALT_SRC" ]; then
    SRC="$ALT_SRC"
  fi
fi
ICO=${2:-assets/icons/virtuoso.ico}
ICNS=${3:-assets/icons/virtuoso.icns}

if [ ! -f "$SRC" ]; then
  echo "Source icon not found: $SRC"
  echo "Provide a PNG source file, e.g. assets/icons/virtuoso.png or asset/icons/virtuoso.png"
  exit 1
fi

if command -v magick >/dev/null 2>&1; then
  CONVERT=magick
elif command -v convert >/dev/null 2>&1; then
  CONVERT=convert
else
  echo "ImageMagick not found. Install it to convert icons."
  exit 1
fi

echo "Generating icon files from $SRC"
mkdir -p assets/icons

# Create a multi-resolution ICO
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
$CONVERT "$SRC" -resize 16x16 "$TMPDIR/icon_16x16.png"
$CONVERT "$SRC" -resize 32x32 "$TMPDIR/icon_32x32.png"
$CONVERT "$SRC" -resize 48x48 "$TMPDIR/icon_48x48.png"
$CONVERT "$SRC" -resize 64x64 "$TMPDIR/icon_64x64.png"
$CONVERT "$SRC" -resize 128x128 "$TMPDIR/icon_128x128.png"
$CONVERT "$SRC" -resize 256x256 "$TMPDIR/icon_256x256.png"
$CONVERT "$SRC" -resize 512x512 "$TMPDIR/icon_512x512.png"

$CONVERT "$TMPDIR/icon_16x16.png" "$TMPDIR/icon_32x32.png" "$TMPDIR/icon_48x48.png" \
    "$TMPDIR/icon_64x64.png" "$TMPDIR/icon_128x128.png" "$TMPDIR/icon_256x256.png" \
    "$TMPDIR/icon_512x512.png" "$ICO"

if command -v iconutil >/dev/null 2>&1; then
  ICONSET="$TMPDIR/virtioso.iconset"
  mkdir -p "$ICONSET"
  cp "$TMPDIR/icon_16x16.png" "$ICONSET/icon_16x16.png"
  cp "$TMPDIR/icon_32x32.png" "$ICONSET/icon_16x16@2x.png"
  cp "$TMPDIR/icon_32x32.png" "$ICONSET/icon_32x32.png"
  cp "$TMPDIR/icon_64x64.png" "$ICONSET/icon_32x32@2x.png"
  cp "$TMPDIR/icon_128x128.png" "$ICONSET/icon_128x128.png"
  cp "$TMPDIR/icon_256x256.png" "$ICONSET/icon_128x128@2x.png"
  cp "$TMPDIR/icon_256x256.png" "$ICONSET/icon_256x256.png"
  cp "$TMPDIR/icon_512x512.png" "$ICONSET/icon_256x256@2x.png"
  $CONVERT "$SRC" -resize 1024x1024 "$ICONSET/icon_512x512@2x.png"
  iconutil -c icns -o "$ICNS" "$ICONSET"
  echo "Created $ICNS"
else
  echo "iconutil not found; skipping .icns generation."
fi

printf "Created %s\n" "$ICO"
