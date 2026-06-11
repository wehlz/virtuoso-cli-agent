#!/usr/bin/env python3
"""Run SWE-bench Lite locally against Virtuoso CLI Agent."""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import types
from datetime import datetime
from pathlib import Path

REQUIRED_DISK_GB = 120
RECOMMENDED_RAM_GB = 16
RECOMMENDED_CPU = 8
DEFAULT_DATASET_NAME = "SWE-bench/SWE-bench_Lite"
DEFAULT_SPLIT = "test"
DEFAULT_RESULTS_DIR = Path("swe_bench_results")
DEFAULT_WORKDIR = Path("swe_bench_workdir")
DEFAULT_TIMEOUT = 30 * 60
DEFAULT_PARALLELISM = 1


def _ensure_windows_resource_module() -> None:
    if platform.system() != "Windows":
        return

    if "resource" in sys.modules:
        return

    resource = types.ModuleType("resource")
    resource.RLIMIT_NOFILE = 1
    resource.RLIMIT_AS = 2
    resource.RLIMIT_CPU = 0
    resource.RLIM_INFINITY = -1
    resource.getrlimit = lambda *args: (resource.RLIM_INFINITY, resource.RLIM_INFINITY)
    resource.setrlimit = lambda *args, **kwargs: None
    sys.modules["resource"] = resource


def check_prerequisites(skip_disk: bool = False) -> None:
    print("Checking prerequisites...")
    if shutil.which("docker") is None:
        raise RuntimeError("Docker CLI not found. Install Docker Desktop / Docker Engine and retry.")

    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Docker daemon is not running or not reachable. Run Docker and retry.\n{exc.stderr.strip()}"
        )

    if shutil.which("git") is None:
        raise RuntimeError("git is required but not installed. Install git and retry.")

    if not skip_disk:
        total, used, free = shutil.disk_usage(Path.cwd())
        free_gb = free / 1024 ** 3
        print(f"Free disk: {free_gb:.1f} GB")
        if free_gb < REQUIRED_DISK_GB:
            raise RuntimeError(
                f"Not enough free disk space. At least {REQUIRED_DISK_GB} GB free is recommended."
            )

    cpu_count = os.cpu_count() or 1
    print(f"CPU cores: {cpu_count}")
    if cpu_count < RECOMMENDED_CPU:
        print(
            f"Warning: {cpu_count} CPU cores detected. {RECOMMENDED_CPU} cores are recommended for SWE-bench."
        )

    ram_gb = _get_total_ram_gb()
    print(f"System RAM: {ram_gb:.1f} GB")
    if ram_gb < RECOMMENDED_RAM_GB:
        print(
            f"Warning: {ram_gb:.1f} GB RAM detected. {RECOMMENDED_RAM_GB} GB is recommended for SWE-bench."
        )


def _get_total_ram_gb() -> float:
    if platform.system() == "Windows":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return stat.ullTotalPhys / 1024 ** 3
        except Exception:
            return 0.0

    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return pages * page_size / 1024 ** 3
        except Exception:
            pass

    return 0.0


def install_dependencies() -> None:
    print("Installing SWE-bench dependencies...")
    _ensure_windows_resource_module()
    try:
        import swebench  # noqa: F401
    except Exception:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "swebench", "docker"],
            check=True,
        )


def load_swebench_instances(dataset_name: str, split: str, instance_ids: list[str] | None):
    _ensure_windows_resource_module()
    from swebench.harness.utils import load_swebench_dataset

    print(f"Loading dataset {dataset_name} split={split}...")
    return load_swebench_dataset(dataset_name, split, instance_ids)


def build_predictions(
    instances: list[dict],
    workdir: Path,
    patches_dir: Path,
    timeout: int,
) -> dict:
    from core.swe_bench_adapter import run_virtuoso_on_instance
    from swebench.harness.constants import KEY_MODEL, KEY_INSTANCE_ID, KEY_PREDICTION

    patches_dir.mkdir(parents=True, exist_ok=True)
    predictions = {}
    for instance in instances:
        instance_id = instance["instance_id"]
        print(f"\n=== Generating patch for {instance_id} ===")
        try:
            patch_path = run_virtuoso_on_instance(instance, str(workdir / instance_id), timeout=timeout)
            patch_text = Path(patch_path).read_text(encoding="utf-8")
            predictions[instance_id] = {
                KEY_INSTANCE_ID: instance_id,
                KEY_MODEL: "virtuoso-cli",
                KEY_PREDICTION: patch_text,
            }
            patch_file = patches_dir / f"{instance_id}.patch"
            patch_file.write_text(patch_text, encoding="utf-8")
            print(f"Saved patch for {instance_id} to {patch_file}")
        except Exception as exc:
            print(f"Failed to generate patch for {instance_id}: {exc}")
            predictions[instance_id] = {
                KEY_INSTANCE_ID: instance_id,
                KEY_MODEL: "virtuoso-cli",
                KEY_PREDICTION: "",
            }
    return predictions


def patch_swebench_log_dir(results_dir: Path) -> None:
    _ensure_windows_resource_module()
    from pathlib import Path as P
    import swebench.harness.run_evaluation as swe_run_eval
    import swebench.harness.constants as swe_constants

    target_log_dir = results_dir / "logs" / "run_evaluation"
    swe_constants.RUN_EVALUATION_LOG_DIR = target_log_dir
    swe_run_eval.RUN_EVALUATION_LOG_DIR = target_log_dir


def run_evaluation(
    predictions: dict,
    instances: list[dict],
    results_dir: Path,
    parallelism: int,
    timeout: int,
    run_id: str,
) -> None:
    _ensure_windows_resource_module()
    from swebench.harness.run_evaluation import run_instances

    print("Starting SWE-bench evaluation... this may take a long time.")
    patch_swebench_log_dir(results_dir)
    run_instances(
        predictions=predictions,
        instances=instances,
        cache_level="medium",
        clean=False,
        force_rebuild=False,
        max_workers=parallelism,
        run_id=run_id,
        timeout=timeout,
        namespace="virtuoso",
        instance_image_tag="latest",
        env_image_tag="latest",
        rewrite_reports=False,
    )


def summarize_results(results_dir: Path, run_id: str) -> dict:
    report_root = results_dir / "logs" / "run_evaluation" / run_id / "virtuoso"
    summary = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "instances": [],
        "resolved": 0,
        "total": 0,
    }
    if not report_root.exists():
        print(f"Warning: report directory not found: {report_root}")
        return summary

    for instance_dir in sorted(report_root.iterdir()):
        if not instance_dir.is_dir():
            continue
        report_file = instance_dir / "report.json"
        test_output = instance_dir / "test_output.txt"
        patch_file = results_dir / "patches" / f"{instance_dir.name}.patch"
        resolved = False
        report_text = None
        if report_file.exists():
            report_text = json.loads(report_file.read_text(encoding="utf-8"))
            instance_report = report_text.get(instance_dir.name, {})
            resolved = instance_report.get("resolved", False)
        summary["instances"].append(
            {
                "instance_id": instance_dir.name,
                "resolved": bool(resolved),
                "patch_path": str(patch_file) if patch_file.exists() else None,
                "report_path": str(report_file) if report_file.exists() else None,
                "test_output_path": str(test_output) if test_output.exists() else None,
            }
        )
        summary["resolved"] += 1 if resolved else 0
        summary["total"] += 1

    summary["resolution_rate"] = (
        summary["resolved"] / summary["total"] * 100 if summary["total"] else 0.0
    )
    return summary


def parse_instance_ids(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def make_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run SWE-bench Lite evaluation against Virtuoso CLI Agent."
    )
    parser.add_argument(
        "--dataset-name",
        default=DEFAULT_DATASET_NAME,
        help="SWE-bench dataset identifier or local path.",
    )
    parser.add_argument(
        "--split",
        default=DEFAULT_SPLIT,
        help="Dataset split to evaluate.",
    )
    parser.add_argument(
        "--subset",
        type=int,
        default=10,
        help="Number of instances to evaluate for a smoke test.",
    )
    parser.add_argument(
        "--instance-ids",
        type=parse_instance_ids,
        default=None,
        help="Comma-separated instance IDs to evaluate.",
    )
    parser.add_argument(
        "--results-dir",
        default=str(DEFAULT_RESULTS_DIR),
        help="Directory to save logs, patches, and reports.",
    )
    parser.add_argument(
        "--workdir",
        default=str(DEFAULT_WORKDIR),
        help="Temporary workspace for instance checkouts.",
    )
    parser.add_argument(
        "--parallelism",
        type=int,
        default=DEFAULT_PARALLELISM,
        help="Number of concurrent Docker evaluations.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Timeout per instance in seconds.",
    )
    parser.add_argument(
        "--skip-disk-check",
        action="store_true",
        help="Skip the 120GB disk free prerequisite check.",
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="Skip automatic dependency installation.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even when RAM is below the recommended minimum.",
    )
    return parser


def _abort_if_unsuitable_machine(force: bool) -> None:
    if force:
        return
    ram_gb = _get_total_ram_gb()
    if ram_gb < RECOMMENDED_RAM_GB:
        raise SystemExit(
            f"\nSWE-bench needs Docker, ~120GB disk, and {RECOMMENDED_RAM_GB}+ GB RAM "
            f"(detected {ram_gb:.1f} GB).\n"
            "Virtuoso daily use does not require SWE-bench — use `python virtuoso.py` with Gemini.\n"
            "To run anyway: python scripts/run_swe_bench.py --force\n"
        )


def main() -> int:
    args = make_argument_parser().parse_args()
    _abort_if_unsuitable_machine(force=getattr(args, "force", False))
    results_dir = Path(args.results_dir).resolve()
    workdir = Path(args.workdir).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    workdir.mkdir(parents=True, exist_ok=True)

    if not args.no_install:
        install_dependencies()

    check_prerequisites(skip_disk=args.skip_disk_check)

    instances = load_swebench_instances(
        args.dataset_name,
        args.split,
        args.instance_ids,
    )
    if args.subset and args.subset < len(instances):
        instances = instances[: args.subset]

    print(f"Preparing {len(instances)} instances for evaluation...")
    patches_dir = results_dir / "patches"
    predictions = build_predictions(
        instances=instances,
        workdir=workdir,
        patches_dir=patches_dir,
        timeout=args.timeout,
    )

    run_id = datetime.utcnow().strftime("virtuoso_swebench_%Y%m%d_%H%M%S")
    run_evaluation(
        predictions=predictions,
        instances=instances,
        results_dir=results_dir,
        parallelism=args.parallelism,
        timeout=args.timeout,
        run_id=run_id,
    )

    summary = summarize_results(results_dir, run_id)
    summary_path = results_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== SWE-bench summary ===")
    print(f"Resolved: {summary['resolved']} / {summary['total']} ({summary['resolution_rate']:.2f}%)")
    print(f"Reports: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
