#!/usr/bin/env python3
"""
core/sandbox.py
Lightweight sandbox utilities for Virtuoso Phase 3.

Runs commands in a temporary directory with time and memory limits.
"""
import os
import sys
import tempfile
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple

try:
    import resource
except Exception:
    resource = None


class LightweightSandbox:
    """
    Minimal sandbox using temporary directory, subprocess, and resource limits.
    No Docker – runs in a separate process with restricted resources where possible.
    """
    def __init__(self, timeout_sec: int = 10, max_memory_mb: int = 512, max_disk_mb: int = 100):
        self.timeout_sec = timeout_sec
        self.max_memory_mb = max_memory_mb
        self.max_disk_mb = max_disk_mb
        self.temp_dir = None

    def __enter__(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="virtuoso_sandbox_")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir:
            try:
                self.temp_dir.cleanup()
            except Exception:
                pass

    def write_file(self, filename: str, content: str) -> str:
        path = Path(self.temp_dir.name) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return str(path)

    def read_file(self, filename: str) -> str:
        path = Path(self.temp_dir.name) / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _set_limits(self):
        # Only available on Unix-like systems
        if resource is None:
            return
        # Memory limit (address space)
        try:
            resource.setrlimit(resource.RLIMIT_AS, (self.max_memory_mb * 1024 * 1024, self.max_memory_mb * 1024 * 1024))
        except Exception:
            pass

        # CPU time (seconds)
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (self.timeout_sec, self.timeout_sec))
        except Exception:
            pass

    def run_command(self, cmd: str, cwd: Optional[str] = None) -> Tuple[str, str, int]:
        """
        Run a shell command inside sandbox with resource limits.
        Returns (stdout, stderr, returncode).
        """
        if cwd is None:
            cwd = self.temp_dir.name
        else:
            cwd = str(Path(self.temp_dir.name) / cwd)

        preexec = None
        if sys.platform != "win32" and resource is not None:
            def _preexec():
                self._set_limits()
            preexec = _preexec

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
                preexec_fn=preexec
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", f"Command timed out after {self.timeout_sec} seconds", -1
        except Exception as e:
            return "", f"Sandbox error: {e}", -1

    def run_python(self, code: str) -> Tuple[str, str, int]:
        """Run Python code inside sandbox as a script."""
        # Strip markdown fences if present
        if code.strip().startswith("```"):
            parts = code.split('```')
            # take last part
            code = parts[-1]
        script_path = self.write_file("temp_script.py", code)
        return self.run_command(f"{sys.executable} {script_path}")

    def check_disk_usage(self) -> bool:
        """Ensure sandbox disk usage is within limit."""
        total = 0
        for root, dirs, files in os.walk(self.temp_dir.name):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except Exception:
                    continue
        return total <= (self.max_disk_mb * 1024 * 1024)


# Simple dangerous command heuristics
DANGEROUS_COMMAND_PATTERNS = [
    "rm -rf", "rm -r", ":(){:|:&};:", "mkfs", "dd if=", "> /dev/", "curl .*sh", "wget .* -O-", "nc -e", "sh -i",
]

def is_dangerous(cmd: str) -> bool:
    cmd_lower = (cmd or "").lower()
    for p in DANGEROUS_COMMAND_PATTERNS:
        if p in cmd_lower:
            return True
    return False


def ask_permission(cmd: str) -> bool:
    print(f"\n⚠️  Potentially dangerous command: {cmd}")
    try:
        response = input("Allow? (y/N): ").strip().lower()
        return response == 'y'
    except Exception:
        return False
