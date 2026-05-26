#!/usr/bin/env python3
"""Request a non-destructive FL Studio MIDI scripting capability probe."""

import argparse
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
MIDI_SCRIPT_NAME = "NovationLaunchpadProMK3Midi"
DAW_SCRIPT_NAME = "NovationLaunchpadProMK3DAW"
REQUEST_FILE = "capability_probe_request.json"
RESULT_FILE = "capability_probe_results.jsonl"


def default_hardware_dir():
    return Path.home() / "Documents/Image-Line/FL Studio/Settings/Hardware"


def install_scripts(hardware_dir):
    for script_name in (MIDI_SCRIPT_NAME, DAW_SCRIPT_NAME):
        src = REPO_DIR / "hardware" / script_name
        dst = hardware_dir / script_name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)


def write_probe_request(script_dir):
    request_id = str(uuid.uuid4())
    request = {
        "request_id": request_id,
        "created_at": time.time(),
        "created_by": "request-fl-capability-probe.py",
        "probe": "launchpad_capability_probe",
    }
    script_dir.mkdir(parents=True, exist_ok=True)
    request_path = script_dir / REQUEST_FILE
    request_path.write_text(json.dumps(request, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return request_id, request_path


def find_result(result_path, request_id):
    if not result_path.exists():
        return None
    for line in result_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            continue
        if result.get("request", {}).get("request_id") == request_id:
            return result
    return None


def wait_for_result(result_path, request_id, timeout_seconds):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        result = find_result(result_path, request_id)
        if result is not None:
            return result
        time.sleep(0.5)
    return None


def retire_request_file(request_path, request_id):
    if not request_path.exists():
        return

    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        request = {}

    if request.get("request_id") != request_id:
        return

    request_path.replace(request_path.with_name(f"{REQUEST_FILE}.last-run-{request_id}"))


def open_fl_studio(app_name):
    subprocess.run(["open", "-a", app_name], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hardware-dir",
        type=Path,
        default=default_hardware_dir(),
        help="FL Studio Hardware folder. Defaults to the macOS user data location.",
    )
    parser.add_argument("--install", action="store_true", help="Copy repo scripts into the Hardware folder first.")
    parser.add_argument("--open-fl", action="store_true", help="Open FL Studio after writing the request.")
    parser.add_argument("--fl-app", default="FL Studio 2025", help="Application name used with macOS open -a.")
    parser.add_argument("--wait", type=float, default=0, help="Seconds to wait for the JSONL result.")
    args = parser.parse_args()

    hardware_dir = args.hardware_dir.expanduser()
    if args.install:
        install_scripts(hardware_dir)

    script_dir = hardware_dir / MIDI_SCRIPT_NAME
    request_id, request_path = write_probe_request(script_dir)
    result_path = script_dir / RESULT_FILE

    print(f"wrote request: {request_path}")
    print(f"request_id: {request_id}")

    if args.open_fl:
        open_fl_studio(args.fl_app)

    if args.wait > 0:
        result = wait_for_result(result_path, request_id, args.wait)
        if result is None:
            print(f"timed out waiting for result: {result_path}", file=sys.stderr)
            return 2
        retire_request_file(request_path, request_id)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
