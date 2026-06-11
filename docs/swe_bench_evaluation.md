# Evaluating Virtuoso with SWE-bench Lite

This guide explains how to run a local SWE-bench Lite evaluation for Virtuoso CLI Agent.
The evaluation is designed to measure how often Virtuoso produces patches that fix real-world open-source issues.

## Prerequisites

- Docker Desktop / Docker Engine installed and running
- Python 3.10 or newer
- `git` installed and available on `PATH`
- At least 120GB free disk space recommended
- At least 16GB RAM and 8 CPU cores recommended

> On Windows, Docker Desktop should be configured to use Linux containers.

## Setup

1. Open a terminal in the repository root:

```bash
cd path/to/virtuoso-cli-agent
```

2. Run the evaluation wrapper for a quick smoke test:

```bash
bash scripts/run_swe_bench.sh --subset 10
```

On Windows:

```powershell
scripts\run_swe_bench.bat --subset 10
```

The first run may download the SWE-bench Lite dataset and create helper files.

## Running the Full Evaluation

For a full SWE-bench Lite evaluation, omit `--subset` or set it to `300`:

```bash
bash scripts/run_swe_bench.sh
```

On Windows:

```powershell
scripts\run_swe_bench.bat
```

## How the evaluation works

The runner performs these steps:

1. Verifies Docker, git, and local resource requirements
2. Installs `swebench` and its Python dependencies if needed
3. Loads SWE-bench Lite from Hugging Face or a local dataset path
4. Clones each task repository and checks out the base commit
5. Runs Virtuoso in a sandboxed repo checkout and generates a patch
6. Applies the patch inside the SWE-bench Docker container
7. Executes the task test harness and records the result

## Results

Evaluation outputs are stored in `swe_bench_results/`.

The runner saves:

- `swe_bench_results/patches/` — generated patch files for each instance
- `swe_bench_results/summary.json` — resolution rate and per-instance summary
- `swe_bench_results/logs/run_evaluation/` — SWE-bench evaluation logs and reports

### Interpreting the score

- `resolution_rate` is the percentage of instances where Virtuoso produced a patch that passed all tests.
- A low score can indicate weaknesses in:
  - task understanding or localization of the requested fix
  - patch generation format
  - test-driven debugging and patch correctness

## Troubleshooting

### Docker issues

- Ensure Docker Desktop is running.
- On Windows, confirm Docker is using Linux containers.
- If `docker info` fails, restart Docker and rerun the script.

### Memory or disk warnings

- The runner checks available disk space and will warn if the system has less than 120GB.
- If your machine has less than 16GB RAM, reduce `--parallelism` to `1`.

### Timeouts

- The command uses a default per-instance timeout of 30 minutes.
- To increase or decrease the timeout, pass `--timeout`.

```bash
bash scripts/run_swe_bench.sh --subset 10 --timeout 3600
```

### SWE-bench package import on Windows

The evaluation script automatically applies a small compatibility shim so the `swebench` package can import on Windows.
If `swebench` fails to import, ensure your Python environment is clean and reinstall dependencies.

## Notes

- The evaluation is local and does not submit any data externally unless you explicitly upload results.
- The script is intended for reproducibility and can be re-run after interruption.
- For debugging, start with `--subset 5` or `--subset 10` before running the full set.
