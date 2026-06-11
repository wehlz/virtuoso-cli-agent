#!/usr/bin/env python3
"""Adapter layer that runs Virtuoso against SWE-bench instances."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

RESOURCE_HINT = (
    "Virtuoso outputs code blocks with a file path comment at the top, "
    "for example: # src/module.py"
)

PATCH_HEADER_PATTERN = re.compile(r"^diff --git", re.MULTILINE)
FILE_PATH_COMMENT_PATTERN = re.compile(
    r"^(?:#|//)\s*(?P<path>[A-Za-z0-9_./\\-]+)(?::)?$"
)


def _normalize_patch_dir(repo_root: Path, path: str) -> Path:
    candidate = Path(path.strip())
    if candidate.is_absolute():
        target = candidate
    else:
        target = repo_root / candidate
    try:
        target = target.resolve()
        target.relative_to(repo_root.resolve())
    except Exception:
        raise ValueError(f"Patch target path is outside repo: {path}")
    return target


def _quote_prompt(prompt: str) -> str:
    sanitized = prompt.strip().replace("\n", " ").replace("\r", " ")
    return sanitized


def _run_virtuoso_build(repo_path: Path, problem: str, timeout: int = 1800) -> str:
    python_exe = sys.executable
    virtuoso_script = Path(__file__).resolve().parents[1] / "virtuoso.py"
    if not virtuoso_script.exists():
        raise FileNotFoundError(f"Could not locate virtuoso.py at {virtuoso_script}")

    prompt = _quote_prompt(problem)
    command = [python_exe, str(virtuoso_script)]
    stdin = f"/build {prompt}\n/exit\n"
    result = subprocess.run(
        command,
        cwd=repo_path,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = result.stdout + "\n" + result.stderr
    if result.returncode != 0:
        raise RuntimeError(
            f"Virtuoso exited with code {result.returncode}.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return output


def _find_final_code(output: str) -> str:
    marker = "📦 Final Code:"
    if marker in output:
        candidate = output.split(marker, 1)[1]
    else:
        candidate = output
    return candidate.strip()


def _extract_file_blocks(code: str) -> List[Tuple[str, str]]:
    blocks: List[Tuple[str, str]] = []
    current_path: Optional[str] = None
    current_lines: List[str] = []
    for raw_line in code.splitlines():
        line = raw_line.rstrip()
        match = FILE_PATH_COMMENT_PATTERN.match(line.strip())
        if match and "/" in match.group("path"):
            if current_path is not None:
                blocks.append((current_path, "\n".join(current_lines).rstrip() + "\n"))
            current_path = match.group("path")
            current_lines = []
        elif current_path is not None:
            current_lines.append(line)

    if current_path is not None:
        blocks.append((current_path, "\n".join(current_lines).rstrip() + "\n"))
    return blocks


def _is_patch_text(candidate: str) -> bool:
    return bool(PATCH_HEADER_PATTERN.search(candidate))


def _write_generated_files(repo_path: Path, blocks: List[Tuple[str, str]]) -> None:
    if not blocks:
        raise ValueError("No file blocks found in generated code.")
    for relative_path, content in blocks:
        target = _normalize_patch_dir(repo_path, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _git_diff(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "diff", "--no-color", "--"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    diff_text = result.stdout.strip()
    if not diff_text:
        raise RuntimeError("No diff was produced after applying generated code.")
    return diff_text


def _checkout_repo(instance: Dict[str, str], workdir: Path) -> Path:
    repo_url = instance["repo"]
    commit = instance.get("base_commit")
    if not repo_url:
        raise ValueError("Instance missing repo URL")
    repo_path = workdir.resolve()
    if repo_path.exists():
        shutil.rmtree(repo_path)
    repo_path.mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "clone", repo_url, str(repo_path)], check=True)
    if commit:
        subprocess.run(["git", "checkout", commit], cwd=repo_path, check=True)
    return repo_path


def run_virtuoso_on_instance(instance: Dict[str, str], workdir: str) -> str:
    """Run Virtuoso on a SWE-bench instance and return the patch file path."""
    workdir_path = Path(workdir).resolve()
    workdir_path.mkdir(parents=True, exist_ok=True)
    repo_path = _checkout_repo(instance, workdir_path)

    problem = instance.get("problem_statement", "")
    hints = instance.get("hints_text")
    if hints:
        problem = f"{problem}\n\nHints: {hints}"

    output = _run_virtuoso_build(repo_path, problem)
    code = _find_final_code(output)

    if _is_patch_text(code):
        patch_path = workdir_path / "virtuso_generated.patch"
        patch_path.write_text(code, encoding="utf-8")
        return str(patch_path)

    blocks = _extract_file_blocks(code)
    if not blocks:
        raise RuntimeError(
            "Could not identify a patch or file update from Virtuoso output. "
            f"{RESOURCE_HINT}"
        )

    _write_generated_files(repo_path, blocks)
    patch_text = _git_diff(repo_path)
    patch_path = workdir_path / "virtuoso_generated.patch"
    patch_path.write_text(patch_text, encoding="utf-8")
    return str(patch_path)
