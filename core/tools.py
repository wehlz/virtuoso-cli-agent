# core/tools.py
import subprocess
import os
from pathlib import Path
from typing import List, Optional


def has_ripgrep() -> bool:
    """Check if rg is installed."""
    try:
        subprocess.run(["rg", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def grep(pattern: str, path: str = ".", max_count: int = 20) -> List[str]:
    """
    Search for pattern in files (using ripgrep if available, else fallback to Python).
    Returns list of lines with file:line:content.
    """
    if has_ripgrep():
        try:
            result = subprocess.run(
                ["rg", "--line-number", "--max-count", str(max_count), pattern, path],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout.splitlines()
        except subprocess.TimeoutExpired:
            return ["Error: rg search timed out"]
    else:
        matches = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.go', '.rs', '.c', '.cpp', '.txt', '.md')):
                    filepath = Path(root) / file
                    try:
                        with open(filepath, 'r', errors='ignore') as f:
                            for i, line in enumerate(f, 1):
                                if pattern in line:
                                    matches.append(f"{filepath}:{i}:{line.strip()}")
                                    if len(matches) >= max_count:
                                        return matches
                    except Exception:
                        continue
        return matches


def glob_files(pattern: str, path: str = ".") -> List[str]:
    """Find files matching pattern (e.g., '**/*.py')."""
    import glob
    return glob.glob(f"{path}/{pattern}", recursive=True)


def read_file(filepath: str, start_line: int = 1, end_line: Optional[int] = None) -> str:
    """Read file or a specific range of lines."""
    try:
        with open(filepath, 'r', errors='ignore') as f:
            lines = f.readlines()
        if end_line is None:
            end_line = len(lines)
        start_line = max(1, start_line)
        end_line = min(len(lines), end_line)
        return ''.join(lines[start_line-1:end_line])
    except Exception as e:
        return f"Error reading file: {e}"
