#!/bin/zsh
set -euo pipefail

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
hardware_dir="$HOME/Documents/Image-Line/FL Studio/Settings/Hardware"

if pgrep -fl "FL Studio|OsxFL" >/dev/null; then
  echo "FL Studio appears to be running. Quit FL Studio before installing this script." >&2
  exit 1
fi

mkdir -p "$hardware_dir"

for script_name in "Novation Launchpad Pro MK3 Hybrid" "Novation Launchpad Pro MK3 Hybrid DAW"; do
  src="$repo_dir/hardware/$script_name"
  dst="$hardware_dir/$script_name"
  rm -rf "$dst"
  cp -R "$src" "$dst"
  echo "Installed to: $dst"
done
