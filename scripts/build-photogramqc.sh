#!/usr/bin/env bash
# Local Mac / Linux build. CI uses the same PyInstaller spec.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
  echo "ERROR: Python tkinter is missing."
  echo "  macOS: install Python from python.org (includes Tk)"
  echo "  Debian/Ubuntu: sudo apt install python3-tk python3-venv"
  exit 1
fi

python3 -m pip install -r "$root/requirements-build.txt"
python3 -m PyInstaller --noconfirm --clean "$root/PhotogramQC.spec"

if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "Built: $root/dist/PhotogramQC.app"
else
  echo "Built: $root/dist/PhotogramQC"
fi
