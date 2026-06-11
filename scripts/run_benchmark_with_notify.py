#!/usr/bin/env python3
"""Run SWE-bench Verified Mini with logging, progress streaming, and optional notification."""

import argparse
import json
import os
import platform
import re
import smtplib
import sys
import time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from subprocess import PIPE, Popen

DEFAULT_MAX_WORKERS = 2
DEFAULT_RESULTS_DIR = Path("swe_bench_results")
DEFAULT_DATASET_NAME = "SWE-bench/SWE-bench_Verified_Mini"
DEFAULT_SUBSET = 50
LOG_FILENAME = "full_run.log"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the SWE-bench Verified Mini evaluation and notify when complete."
    )
    parser.add_argument(
        "--max_workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help="Number of concurrent Docker evaluations to run.",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Show a desktop notification when the benchmark finishes.",
    )
    parser.add_argument(
        "--email",
        help="Email address to notify when the benchmark finishes.",
    )
    parser.add_argument(
        "--results_dir",
        default=str(DEFAULT_RESULTS_DIR),
        help="Directory to save benchmark logs and results.",
    )
    parser.add_argument(
        "--dataset_name",
        default=DEFAULT_DATASET_NAME,
        help="SWE-bench dataset identifier to evaluate.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Timeout per instance in seconds.",
    )
    return parser.parse_args()


def notify_user(title: str, message: str) -> None:
    """Try to send a desktop notification, falling back to console output."""
    try:
        from plyer import notification

        notification.notify(title=title, message=message, timeout=10)
        return
    except Exception:
        pass

    if platform.system() == "Windows":
        try:
            from win10toast import ToastNotifier

            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=10)
            return
        except Exception:
            pass

    loud_separator = "=" * 80
    print(loud_separator)
    print(f"{title}\n{message}")
    print(loud_separator)


def send_email(recipient: str, subject: str, body: str) -> None:
    """Send a plain text email using SMTP environment variables."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)
    use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes")

    missing = [name for name, value in (
        ("SMTP_HOST", smtp_host),
        ("SMTP_USER", smtp_user),
        ("SMTP_PASSWORD", smtp_password),
        ("SMTP_FROM", smtp_from),
    ) if not value]
    if missing:
        raise RuntimeError(
            "Missing SMTP environment variables: " + ", ".join(missing) + ". "
            "Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM."
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = recipient
    message.set_content(body)

    if use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as client:
            client.login(smtp_user, smtp_password)
            client.send_message(message)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as client:
            client.starttls()
            client.login(smtp_user, smtp_password)
            client.send_message(message)


def parse_resolution_rate(output_lines: list[str], results_dir: Path) -> dict:
    """Extract resolution rate from output or results summary file."""
    for line in reversed(output_lines):
        match = re.search(r"Resolved:\s+\d+\s*/\s*\d+\s*\((?P<rate>[0-9.]+)%\)", line)
        if match:
            return {
                "resolved": None,
                "total": None,
                "resolution_rate": float(match.group("rate")),
                "source": "stdout",
            }

    summary_path = results_dir / "summary.json"
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            return {
                "resolved": summary.get("resolved"),
                "total": summary.get("total"),
                "resolution_rate": summary.get("resolution_rate"),
                "source": "summary.json",
            }
        except Exception:
            pass

    return {"resolved": None, "total": None, "resolution_rate": None, "source": "none"}


def build_benchmark_command(args: argparse.Namespace, results_dir: Path) -> list[str]:
    """Construct the subprocess command for the SWE-bench runner."""
    script_path = Path(__file__).resolve().parent / "run_swe_bench.py"
    return [
        sys.executable,
        str(script_path),
        "--dataset-name",
        args.dataset_name,
        "--subset",
        str(DEFAULT_SUBSET),
        "--parallelism",
        str(args.max_workers),
        "--timeout",
        str(args.timeout),
        "--results-dir",
        str(results_dir),
    ]


def run_benchmark(args: argparse.Namespace) -> tuple[int, list[str]]:
    results_dir = Path(args.results_dir).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    log_path = results_dir / LOG_FILENAME

    command = build_benchmark_command(args, results_dir)
    print(f"Running benchmark command: {' '.join(command)}")
    print(f"Saving log output to: {log_path}")

    output_lines: list[str] = []
    start_time = time.perf_counter()

    with log_path.open("w", encoding="utf-8", buffering=1) as log_file:
        process = Popen(command, stdout=PIPE, stderr=PIPE, text=True, bufsize=1)

        assert process.stdout is not None
        assert process.stderr is not None

        for stdout_line in process.stdout:
            line = stdout_line.rstrip("\n")
            print(line)
            log_file.write(line + "\n")
            output_lines.append(line)

        for stderr_line in process.stderr:
            line = stderr_line.rstrip("\n")
            print(line, file=sys.stderr)
            log_file.write(line + "\n")
            output_lines.append(line)

        return_code = process.wait()

    elapsed_seconds = time.perf_counter() - start_time
    print(f"Benchmark finished in {elapsed_seconds:.1f} seconds.")
    return return_code, output_lines


def main() -> int:
    args = parse_args()
    results_dir = Path(args.results_dir).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    log_path = results_dir / LOG_FILENAME

    try:
        return_code, output_lines = run_benchmark(args)
        summary = parse_resolution_rate(output_lines, results_dir)

        if summary["resolution_rate"] is not None:
            summary_text = (
                f"Resolution rate: {summary['resolution_rate']:.2f}%"
                + (
                    f" (resolved={summary['resolved']} total={summary['total']})"
                    if summary["resolved"] is not None and summary["total"] is not None
                    else ""
                )
            )
        else:
            summary_text = "Resolution rate not found in benchmark output."

        if return_code == 0:
            final_title = "Virtuoso Benchmark Complete"
            final_message = f"Verified Mini completed. {summary_text}\nLog: {log_path}"
            print(final_message)
            if args.notify:
                notify_user(final_title, final_message)
            if args.email:
                try:
                    send_email(
                        args.email,
                        final_title,
                        f"{final_message}\n\nLog file: {log_path}",
                    )
                    print(f"Email sent to {args.email}.")
                except Exception as exc:
                    print(f"Warning: failed to send email: {exc}")
            return 0

        error_title = "Virtuoso Benchmark Failed"
        error_message = (
            f"Benchmark failed with exit code {return_code}.\nSee log: {log_path}"
        )
        print(error_message, file=sys.stderr)
        if args.notify:
            notify_user(error_title, error_message)
        if args.email:
            try:
                send_email(args.email, error_title, error_message)
            except Exception as exc:
                print(f"Warning: failed to send email: {exc}")
        return return_code

    except Exception as exc:
        failure_message = f"Benchmark wrapper failed: {exc}"
        print(failure_message, file=sys.stderr)
        if args.notify:
            notify_user("Virtuoso Benchmark Wrapper Error", failure_message)
        if args.email:
            try:
                send_email(args.email, "Virtuoso Benchmark Wrapper Error", failure_message)
            except Exception as email_exc:
                print(f"Warning: failed to send email: {email_exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
