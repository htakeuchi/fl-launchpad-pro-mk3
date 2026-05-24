#!/bin/zsh
set -euo pipefail

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
src="$repo_dir/hardware/Novation Launchpad Pro MK3 Hybrid"
dst="$HOME/Documents/Image-Line/FL Studio/Settings/Hardware/Novation Launchpad Pro MK3 Hybrid"

if pgrep -fl "FL Studio|OsxFL" >/dev/null; then
  echo "FL Studio appears to be running. Quit FL Studio before installing this script." >&2
  exit 1
fi

mkdir -p "$(dirname "$dst")"
rm -rf "$dst"
cp -R "$src" "$dst"

echo "Installed to: $dst"

