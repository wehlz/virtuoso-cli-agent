@echo off
cd /d %~dp0\..
if not exist .venv_swebench\Scripts\python.exe (
    python -m venv .venv_swebench
)
call .venv_swebench\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install swebench docker
python scripts\run_swe_bench.py %*
