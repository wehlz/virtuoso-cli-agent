"""Parse build goals for output locations and write generated code to disk."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_WINDOWS_INVALID = '<>:"/\\|?*'


@dataclass
class OutputTarget:
    directory: Path
    folder_name: str | None = None
    filename: str | None = None


def desktop_path() -> Path:
    """User Desktop (handles OneDrive Desktop on Windows)."""
    home = Path.home()
    for candidate in (home / "Desktop", home / "OneDrive" / "Desktop"):
        if candidate.is_dir():
            return candidate
    return home / "Desktop"


def sanitize_name(name: str) -> str:
    cleaned = name.strip().strip("\"'")
    for ch in _WINDOWS_INVALID:
        cleaned = cleaned.replace(ch, "")
    return cleaned.strip() or "output"


def _infer_filename(goal: str, code: str) -> str:
    # Coder agent may put path in first comment line: # path/to/file.py
    for line in code.splitlines()[:5]:
        line = line.strip()
        if line.startswith("#"):
            candidate = line.lstrip("#").strip()
            if candidate.endswith(".py") and "/" not in candidate and "\\" not in candidate:
                return sanitize_name(Path(candidate).name)
            if candidate.endswith(".py"):
                return sanitize_name(Path(candidate).name)

    titled = re.search(
        r"(?:titled|named|called)\s+[\"']?([^\"'\n,.]+)",
        goal,
        re.IGNORECASE,
    )
    if titled:
        stem = sanitize_name(titled.group(1))
        if not stem.lower().endswith(".py"):
            stem = f"{stem}.py"
        return stem

    if re.search(r"\bpython\b", goal, re.IGNORECASE):
        return "script.py"
    return "output.py"


def parse_output_target(goal: str, explicit_path: str | None = None) -> OutputTarget | None:
    """Return where to save build output, or None if goal does not ask for a file path."""
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if path.suffix == ".py":
            return OutputTarget(directory=path.parent, filename=path.name)
        return OutputTarget(directory=path, folder_name=None)

    goal_lower = goal.lower()
    wants_save = any(
        phrase in goal_lower
        for phrase in (
            "on my desktop",
            "to my desktop",
            "on desktop",
            "to desktop",
            "save to",
            "write to",
            "create a file",
            "create file",
            "python file",
            "python document",
            "titled ",
            "named ",
            "called ",
        )
    )
    if not wants_save:
        return None

    base = desktop_path() if "desktop" in goal_lower else Path.cwd()

    folder_match = re.search(
        r"(?:folder|directory)\s+(?:named|called|titled)?\s*[\"']?([^\"'\n,.]+)",
        goal,
        re.IGNORECASE,
    )
    folder_name = sanitize_name(folder_match.group(1)) if folder_match else None

    # "titled ai test math" without "folder" -> use as folder if no .py in name
    if not folder_name:
        titled = re.search(
            r"(?:titled|named|called)\s+[\"']?([^\"'\n,.]+)",
            goal,
            re.IGNORECASE,
        )
        if titled:
            name = sanitize_name(titled.group(1))
            if name.lower().endswith(".py"):
                return OutputTarget(directory=base, filename=name)
            folder_name = name

    return OutputTarget(directory=base, folder_name=folder_name)


def resolve_output_file(target: OutputTarget, goal: str, code: str) -> Path:
    out_dir = target.directory
    if target.folder_name:
        out_dir = out_dir / target.folder_name
    filename = target.filename or _infer_filename(goal, code)
    if not filename.lower().endswith(".py"):
        filename = f"{filename}.py"
    return out_dir / filename


def write_code_output(code: str, goal: str, explicit_path: str | None = None) -> Path | None:
    """Write generated code to disk. Returns path written, or None if no target detected."""
    if not code or not code.strip():
        return None
    target = parse_output_target(goal, explicit_path=explicit_path)
    if target is None and explicit_path is None:
        return None
    if target is None:
        target = parse_output_target("", explicit_path=explicit_path)
    if target is None:
        return None

    out_file = resolve_output_file(target, goal, code)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(code.rstrip() + "\n", encoding="utf-8")
    return out_file.resolve()
