#!/usr/bin/env bash
# Build a portable x86_64 AppImage for BudgetWatch (Linux).
# Requires: Python 3.12+, pip, PySide6, fuse2 (to run appimagetool).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/appimage"
DIST="$ROOT/dist-linux"
APPDIR="$BUILD/BudgetWatch.AppDir"
SPEC="$ROOT/packaging/budgetwatch.spec"
ICON="$ROOT/packaging/icons/budgetwatch.png"
DESKTOP="$ROOT/packaging/appimage/budgetwatch.desktop"
APPRUN="$ROOT/packaging/appimage/AppRun"
OUT="$DIST/BudgetWatch-1.0.0-x86_64.AppImage"
ARCH="${ARCH:-x86_64}"
export ARCH

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
  PIP="$ROOT/.venv/bin/pip"
else
  PYTHON="${PYTHON:-python3}"
  PIP="$PYTHON -m pip"
fi

echo "Using $PYTHON"
"$PYTHON" -c "import PySide6, PySide6.QtCharts; print('PySide6', PySide6.__version__)"

"$PIP" install -q 'pyinstaller>=6.6'

echo "Running PyInstaller..."
rm -rf "$ROOT/build/pyinstaller" "$ROOT/build/pyinstaller-work"
"$PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "$ROOT/build/pyinstaller" \
  --workpath "$ROOT/build/pyinstaller-work" \
  "$SPEC"

BIN_DIR="$ROOT/build/pyinstaller/budgetwatch"
if [[ ! -x "$BIN_DIR/budgetwatch" ]]; then
  echo "PyInstaller did not produce $BIN_DIR/budgetwatch" >&2
  exit 1
fi

echo "Assembling AppDir..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$BIN_DIR" "$APPDIR/usr/lib/budgetwatch"
ln -sfn ../lib/budgetwatch/budgetwatch "$APPDIR/usr/bin/budgetwatch"
cp -f "$ICON" "$APPDIR/budgetwatch.png"
cp -f "$ICON" "$APPDIR/usr/share/icons/hicolor/256x256/apps/budgetwatch.png"
cp -f "$DESKTOP" "$APPDIR/budgetwatch.desktop"
cp -f "$APPRUN" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun" "$APPDIR/usr/lib/budgetwatch/budgetwatch"

TOOL="$ROOT/packaging/tools/appimagetool-x86_64.AppImage"
mkdir -p "$ROOT/packaging/tools"
if [[ ! -x "$TOOL" ]]; then
  echo "Downloading appimagetool..."
  curl -fsSL -o "$TOOL" \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
  chmod +x "$TOOL"
fi

mkdir -p "$DIST"
echo "Packing AppImage..."
# Extract appimagetool if FUSE mount is blocked; --appimage-extract-and-run works either way.
if "$TOOL" --appimage-extract-and-run --no-appstream "$APPDIR" "$OUT"; then
  :
else
  echo "appimagetool mount failed; extracting..."
  EXTRACT_DIR="$BUILD/appimagetool-extracted"
  rm -rf "$EXTRACT_DIR"
  mkdir -p "$EXTRACT_DIR"
  (
    cd "$EXTRACT_DIR"
    "$TOOL" --appimage-extract >/dev/null
    ./squashfs-root/AppRun --no-appstream "$APPDIR" "$OUT"
  )
fi

chmod +x "$OUT"
echo "Wrote $OUT"
ls -lh "$OUT"
