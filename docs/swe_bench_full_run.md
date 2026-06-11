# Running Full SWE-bench Lite Evaluation on Virtuoso

This guide walks you through evaluating Virtuoso against all 300 tasks in SWE-bench Lite locally on your machine.

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 22.04+), macOS 12+, or Windows 11 with WSL2
- **Disk space**: At least 120–150 GB free (includes Docker image layers and dataset caches)
- **RAM**: At least 16 GB (8 GB minimum, but evaluation may be slow)
- **CPU**: x86_64 architecture with 8+ cores recommended (ARM64 may have compatibility issues)
- **Internet**: Required for initial dataset and Docker image downloads

### Software

- Docker Desktop / Docker Engine running and accessible
- Python 3.10 or newer
- `git` installed and on `PATH`
- Virtuoso repository cloned locally

### Time Estimate

Full evaluation of 300 tasks typically takes **24–48 hours** depending on your machine and network. Start with a small subset first.

## Step 1: Verify Prerequisites

Open a terminal in the Virtuoso repository root and run:

```bash
# Check Docker is running
docker info

# Check Python version
python --version

# Check git
git --version

# Check disk space
df -h .   # Linux/macOS
Get-Volume   # Windows PowerShell
```

If Docker isn't running, start Docker Desktop or the Docker daemon. If any tool is missing, install it before proceeding.

## Step 2: Quick Smoke Test (5–10 Tasks)

Before committing 24+ hours to a full run, verify the entire pipeline works with a small subset.

### Run the test:

```bash
# Linux / macOS
bash scripts/run_swe_bench.sh --subset 5

# Windows (PowerShell)
scripts\run_swe_bench.bat --subset 5
```

Or directly with Python:

```bash
python scripts/run_swe_bench.py --subset 5
```

### What to expect:

1. **Dependency installation** (~2–5 min): The script installs `swebench` and `docker` Python packages.
2. **Dataset download** (~1–3 min): First-time only; downloads SWE-bench Lite metadata from Hugging Face.
3. **Repository clones** (~10–30 min): Clones task repositories (e.g., `sympy/sympy`, `django/django`).
4. **Virtuoso patch generation** (~5–15 min): Runs Virtuoso on each task to generate a patch.
5. **Docker container setup** (~5–10 min): Builds task-specific Docker images.
6. **Patch application and testing** (~10–20 min): Applies patches and runs test suites.
7. **Report generation** (~1 min): Summarizes results.

**Total for 5 tasks**: ~30–90 minutes.

### Sample output:

```
Checking prerequisites...
Free disk: 850.3 GB
CPU cores: 16
System RAM: 32.0 GB
Installing SWE-bench dependencies...
Loading dataset SWE-bench/SWE-bench_Lite split=test...
Preparing 5 instances for evaluation...

=== Generating patch for sympy__sympy-20590 ===
Cloning sympy/sympy...
Running Virtuoso...
Generated patch saved to swe_bench_results/patches/sympy__sympy-20590.patch

=== Generating patch for django__django-11283 ===
...
Starting SWE-bench evaluation... this may take a long time.
Running 5 instances...
Evaluation: 80%|████████| 4/5 [00:45<00:15, 10.25s/it]

=== SWE-bench summary ===
Resolved: 2 / 5 (40.00%)
Reports: /path/to/swe_bench_results/summary.json
```

### Verify success:

- No critical errors in the output
- `swe_bench_results/summary.json` exists and contains a valid JSON report
- `swe_bench_results/patches/` contains `.patch` files
- At least one task shows `resolved: true` in the report (though 0 resolved is also acceptable for a smoke test)

If the smoke test completes successfully, proceed to the full evaluation. If it fails, see **Troubleshooting** below.

## Step 3: Run Full Evaluation (300 Tasks)

Once the smoke test passes, run the full evaluation:

### Run the evaluation:

```bash
# Linux / macOS
bash scripts/run_swe_bench.sh

# Windows (PowerShell)
scripts\run_swe_bench.bat

# Or directly with Python (any OS)
python scripts/run_swe_bench.py
```

### Command options:

```bash
# Default: 10 tasks (adjust for your needs)
python scripts/run_swe_bench.py

# Explicitly run all 300 tasks
python scripts/run_swe_bench.py --subset 300

# Run specific instance IDs
python scripts/run_swe_bench.py --instance-ids sympy__sympy-20590,django__django-11283

# Reduce parallel workers (for lower memory usage)
python scripts/run_swe_bench.py --parallelism 1

# Increase timeout per task (default: 1800 seconds = 30 min)
python scripts/run_swe_bench.py --timeout 3600

# Combine options
python scripts/run_swe_bench.py --subset 300 --parallelism 2 --timeout 3600
```

### Starting the full run:

```bash
# Recommended for the full 300 tasks
python scripts/run_swe_bench.py --subset 300 --parallelism 4 --timeout 1800
```

**Time**: ~24–72 hours depending on:
- Machine speed (CPU, disk I/O)
- Network bandwidth (downloading repositories and Docker images)
- Virtuoso's reasoning time per task
- Parallelism level (more workers = faster, but higher memory/disk usage)

> **Tip**: Run this in a `tmux` or `screen` session, or redirect output to a file:
>
> ```bash
> python scripts/run_swe_bench.py --subset 300 > swe_bench_run.log 2>&1 &
> ```

## Step 4: Monitor Progress

The script prints progress in real time. You can also monitor via:

### Watch the log output:

```bash
# If running in background, tail the log
tail -f swe_bench_run.log
```

### Monitor Docker activity:

In another terminal:

```bash
# Watch running containers
docker ps --no-trunc --format "table {{.ID}}\t{{.Image}}\t{{.Status}}"

# Watch overall Docker stats
docker stats

# Count images
docker images | wc -l
```

### Check intermediate results:

```bash
# See patches generated so far
ls -la swe_bench_results/patches/ | wc -l

# Check current summary (updates as tasks complete)
cat swe_bench_results/summary.json | jq '.resolved, .total, .resolution_rate'
```

## Step 5: Interpret Results

### After the evaluation completes:

The script prints a summary:

```
=== SWE-bench summary ===
Resolved: 42 / 300 (14.00%)
Reports: /path/to/swe_bench_results/summary.json
```

### Key metric: **Resolution rate**

- `resolution_rate`: Percentage of tasks where Virtuoso's patch passed all tests
- For reference, typical code agents score 5–20% on SWE-bench Lite
- Higher scores indicate better task understanding, localization, and patch generation

### Detailed results:

```bash
# View the full summary
cat swe_bench_results/summary.json | jq '.'

# Count resolved vs. failed
cat swe_bench_results/summary.json | jq '.instances | map(.resolved) | group_by(.) | map({resolved: .[0], count: length})'

# View a specific task's report
cat swe_bench_results/logs/run_evaluation/virtuoso_swebench_*/virtuoso/*/report.json | jq '.'
```

### Results directory structure:

```
swe_bench_results/
├── summary.json                 # Overall resolution rate
├── patches/                     # Generated .patch files (one per task)
│   ├── sympy__sympy-20590.patch
│   └── ...
└── logs/run_evaluation/         # Full SWE-bench evaluation logs
    └── virtuoso_swebench_YYYYMMDD_HHMMSS/
        └── virtuoso/
            ├── sympy__sympy-20590/
            │   ├── report.json       # Pass/fail verdict
            │   ├── test_output.txt   # Test suite output
            │   └── run_instance.log  # Detailed logs
            └── ...
```

## Step 6: Troubleshooting

### "Not enough free disk space"

**Error**: `Not enough free disk space. At least 120 GB free is recommended.`

**Solution**:
- Clean up old Docker images: `docker system prune -a`
- Use `--cache_level env` to avoid rebuilding base images
- Monitor disk usage: `docker system df`

### "Docker daemon is not running"

**Error**: `Docker daemon is not running or not reachable.`

**Solution**:
- Start Docker Desktop (macOS/Windows)
- Start Docker daemon: `sudo systemctl start docker` (Linux)
- Check: `docker ps`

### "Timeout errors"

**Error**: `Test timed out after 1800 seconds.`

**Meaning**: A single task took too long (likely a large repository with slow tests).

**Solution**:
- Increase timeout: `--timeout 3600` (1 hour)
- The script will record the task as "not resolved" and continue
- You can re-run only that task with a longer timeout

### "Virtuoso patch generation failed"

**Error**: `Failed to generate patch for <instance_id>: ...`

**Meaning**: Virtuoso could not produce a valid patch for that task.

**Solution**:
- This is logged but doesn't stop the evaluation
- The harness records it as "empty patch" (not resolved)
- Check the logs in `swe_bench_results/logs/` for details
- Potential fixes:
  - Increase `--timeout` so Virtuoso has more time to reason
  - Adjust Virtuoso's system prompt or parameters in `virtuoso.yaml`
  - The adapter may need refinement (see `core/swe_bench_adapter.py`)

### "Git or repository checkout failed"

**Error**: `Error in evaluating model for <instance_id>: Git error ...`

**Solution**:
- Check internet connectivity
- Some tasks may use very large repositories (~10 GB)
- Ensure sufficient disk space and patience for cloning

### "Docker image build failure"

**Error**: `BuildImageError: Failed to build Docker image ...`

**Solution**:
- May be a network timeout downloading packages
- Retry: `--force-rebuild` may help (though it's slower)
- Check Docker logs: `docker logs <container_id>`

## Step 7 (Optional): Submit to Public Leaderboard

If you want to compare Virtuoso with other agents on the official SWE-bench leaderboard:

### 1. Install the submission CLI:

```bash
pip install sb-cli
```

### 2. Generate an API key:

```bash
sb-cli gen-api-key your.email@example.com
```

You'll receive a token in your email.

### 3. Set the API key:

```bash
export SWEBENCH_API_KEY="your_token_here"
```

On Windows PowerShell:

```powershell
$env:SWEBENCH_API_KEY = "your_token_here"
```

### 4. Submit predictions:

Before submitting, convert the predictions to the submission format:

```bash
python scripts/run_swe_bench.py --subset 300 \
  --results-dir swe_bench_results
```

Then submit:

```bash
sb-cli submit swe-bench_lite test \
  --predictions_path swe_bench_results/predictions.jsonl \
  --run_id virtuoso_full_eval
```

The CLI will:
- Upload your predictions
- Run official evaluation
- Display your score on the leaderboard
- Provide a public URL (if you opt in)

> **Note**: Your data is only sent if you explicitly submit. The local evaluation is 100% private.

## Resource Usage Notes

### Disk space:

- Dataset cache: ~500 MB
- Cloned repositories: ~50–100 GB (varies; many tasks reuse large repos)
- Docker images: ~20–50 GB
- Patch files: ~100 MB
- Logs: ~1–5 GB
- **Total**: ~70–150 GB

### Memory:

- Each Docker container: ~500 MB – 2 GB
- With `--parallelism 4`: ~2–8 GB peak
- Adjust parallelism if OOM errors occur

### CPU:

- Parallelism multiplies CPU usage
- Higher parallelism = faster but higher resource contention
- Recommended: `--parallelism = (CPU cores / 2)`

## Sample Expected Output

Below is a realistic mock of what you'll see:

```
Checking prerequisites...
Free disk: 850.3 GB
CPU cores: 16
System RAM: 32.0 GB

Installing SWE-bench dependencies...
(dependencies already installed, skipping)

Loading dataset SWE-bench/SWE-bench_Lite split=test...
loaded 300

Preparing 300 instances for evaluation...

=== Generating patch for sympy__sympy-20590 ===
Cloning sympy/sympy...
Running Virtuoso...
Saved patch for sympy__sympy-20590 to swe_bench_results/patches/sympy__sympy-20590.patch

=== Generating patch for django__django-11283 ===
Cloning django/django...
Running Virtuoso...
Saved patch for django__django-11283 to swe_bench_results/patches/django__django-11283.patch

... (297 more tasks) ...

Starting SWE-bench evaluation... this may take a long time.

Running 300 instances...
Evaluation: 45%|████▌     | 135/300 [12:34<15:23, 5.63s/it]

... (hours pass) ...

Evaluation: 100%|██████████| 300/300 [47:23<00:00, 9.48s/it]

All instances run.

=== SWE-bench summary ===
Resolved: 42 / 300 (14.00%)
Reports: /path/to/virtuoso-cli-agent/swe_bench_results/summary.json
```

### Then check detailed results:

```bash
$ cat swe_bench_results/summary.json | jq '{resolved, total, resolution_rate}'

{
  "resolved": 42,
  "total": 300,
  "resolution_rate": 14.0
}

$ ls swe_bench_results/patches | wc -l
300

$ ls swe_bench_results/logs/run_evaluation/virtuoso_*/virtuoso | wc -l
300
```

## Next Steps

After obtaining a baseline resolution rate:

1. **Analyze failures**: Review logs in `swe_bench_results/logs/run_evaluation/` to identify common failure modes.
2. **Iterate**: Improve Virtuoso's reasoning, patch generation, or task understanding.
3. **Re-run**: The script is idempotent; tasks that already have reports are skipped.
4. **Track progress**: Compare resolution rates across iterations to measure improvement.

---

**Questions?** Refer to `docs/swe_bench_evaluation.md` for architecture details or `core/swe_bench_adapter.py` for adapter customization.
