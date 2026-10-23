#!/usr/bin/env bash
# Install BudgetWatch for the current user (no root).
# Copies the AppImage to ~/.local/bin and adds an app-menu launcher.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPIMAGE="$ROOT/dist-linux/BudgetWatch-1.0.0-x86_64.AppImage"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
TARGET="$BIN_DIR/BudgetWatch.AppImage"

if [[ ! -x "$APPIMAGE" ]]; then
  echo "AppImage not found at:"
  echo "  $APPIMAGE"
  echo "Build it first:  bash packaging/build-appimage.sh"
  exit 1
fi

mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"
cp -f "$APPIMAGE" "$TARGET"
chmod +x "$TARGET"
cp -f "$ROOT/packaging/icons/budgetwatch.png" "$ICON_DIR/budgetwatch.png"

cat > "$APP_DIR/budgetwatch.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=BudgetWatch
Comment=Household cash-flow tracker — this month and the next six
Exec=$TARGET
Icon=budgetwatch
Terminal=false
Categories=Office;Finance;
StartupNotify=true
StartupWMClass=budgetwatch
Keywords=budget;bills;paycheck;cashflow;
SingleMainWindow=true
EOF
chmod +x "$APP_DIR/budgetwatch.desktop"
update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true

ln -sfn "$TARGET" "$BIN_DIR/budgetwatch"

echo "Installed BudgetWatch for $USER"
echo "  launcher: $APP_DIR/budgetwatch.desktop"
echo "  command:  budgetwatch"
echo "  file:     $TARGET"
echo
echo "If the AppImage cannot mount (missing FUSE), run:"
echo "  $TARGET --appimage-extract-and-run"
