#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

if [ ! -x "./.venv_swebench/bin/python" ]; then
  python3 -m venv .venv_swebench
fi
source .venv_swebench/bin/activate
python -m pip install --upgrade pip
python -m pip install swebench docker
python scripts/run_swe_bench.py "$@"
