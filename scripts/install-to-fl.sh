#!/bin/zsh
set -euo pipefail

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
hardware_dir="$HOME/Documents/Image-Line/FL Studio/Settings/Hardware"
reg_file="$HOME/Library/Preferences/Image-Line/reg.xml"

if pgrep -fl "FL Studio|OsxFL" >/dev/null; then
  echo "FL Studio appears to be running. Quit FL Studio before installing this script." >&2
  exit 1
fi

mkdir -p "$hardware_dir"

for legacy_name in "Novation Launchpad Pro MK3 Hybrid" "Novation Launchpad Pro MK3 Hybrid DAW"; do
  rm -rf "$hardware_dir/$legacy_name"
done

for script_name in "NovationLaunchpadProMK3Hybrid" "NovationLaunchpadProMK3HybridDAW"; do
  src="$repo_dir/hardware/$script_name"
  dst="$hardware_dir/$script_name"
  rm -rf "$dst"
  cp -R "$src" "$dst"
  echo "Installed to: $dst"
done

if [[ -f "$reg_file" ]]; then
  backup="$reg_file.bak-$(date +%Y%m%d-%H%M%S)"
  cp "$reg_file" "$backup"
  perl -0pi -e 's/Novation Launchpad Pro MK3 Hybrid DAW/NovationLaunchpadProMK3HybridDAW/g; s/Novation Launchpad Pro MK3 Hybrid/NovationLaunchpadProMK3Hybrid/g' "$reg_file"
  echo "Updated ScriptFolder names in: $reg_file"
  echo "Backup: $backup"
fi
