import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def get_data_arg(source: str, target: str) -> str:
    source_path = Path(source).resolve()
    if platform.system() == "Windows":
        return f"{source_path};{target}"
    return f"{source_path}:{target}"


def is_valid_ico(path: Path) -> bool:
    """Return True when path has the basic Windows ICO header."""
    try:
        with path.open("rb") as fh:
            header = fh.read(6)
    except OSError:
        return False
    return len(header) == 6 and header[:4] == b"\x00\x00\x01\x00" and int.from_bytes(header[4:6], "little") > 0


def resolve_bundle_config(root: Path, config_path: Optional[Path] = None) -> Path:
    """Pick config to embed in the executable (default: template without secrets)."""
    if config_path is not None:
        candidate = config_path if config_path.is_absolute() else root / config_path
        if not candidate.exists():
            raise FileNotFoundError(f"Config not found: {candidate}")
        return candidate.resolve()

    example = root / "virtuoso.yaml.example"
    if example.exists():
        return example.resolve()

    user_cfg = root / "virtuoso.yaml"
    if user_cfg.exists():
        print("Warning: bundling virtuoso.yaml (virtuoso.yaml.example not found). Ensure no API keys are set.")
        return user_cfg.resolve()

    raise FileNotFoundError("Neither virtuoso.yaml.example nor virtuoso.yaml found in project root.")


def build(
    entry_script: Path,
    name: str = "virtuoso",
    dist_dir: Path = Path("dist"),
    icon_path: Optional[str] = None,
    config_path: Optional[Path] = None,
) -> int:
    dist_dir.mkdir(parents=True, exist_ok=True)
    spec_dir = Path("build")
    spec_dir.mkdir(parents=True, exist_ok=True)

    icon_file = None
    if icon_path:
        candidate = Path(icon_path)
        if candidate.exists():
            icon_file = str(candidate.resolve())
        else:
            print(f"Warning: Icon file passed but not found: {icon_path}")
    else:
        icon_dirs = [Path("assets/icons"), Path("asset/icons")]
        if sys.platform == "win32":
            icon_candidates = ["virtuoso.ico"]
            for icon_dir in icon_dirs:
                for icon_name in icon_candidates:
                    candidate = icon_dir / icon_name
                    if candidate.exists() and is_valid_ico(candidate):
                        icon_file = str(candidate.resolve())
                        break
                    if candidate.exists():
                        print(f"Warning: Icon file is not a valid .ico and will be skipped: {candidate}")
                if icon_file:
                    break
        elif sys.platform == "darwin":
            for icon_dir in icon_dirs:
                candidate = icon_dir / "virtuoso.icns"
                if candidate.exists():
                    icon_file = str(candidate.resolve())
                    break

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--noconfirm",
        "--clean",
        f"--name={name}",
        f"--distpath={dist_dir}",
        f"--workpath={spec_dir / 'build' }",
        f"--specpath={spec_dir}",
        str(entry_script),
    ]

    if icon_file:
        cmd.extend(["--icon", icon_file])
    else:
        print("Warning: No icon file found; building without custom icon.")

    root = entry_script.parent
    bundle_config = resolve_bundle_config(root, config_path)
    staged_config = spec_dir / "staging" / "virtuoso.yaml"
    staged_config.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bundle_config, staged_config)
    print(f"Bundling config from {bundle_config.name} (embedded as virtuoso.yaml)")
    cmd.extend(["--add-data", get_data_arg(str(staged_config), ".")])

    # Include the TUI package and any non-python assets
    cmd.extend(["--add-data", get_data_arg("virtuoso_tui", "virtuoso_tui")])
    cmd.extend(["--add-data", get_data_arg("virtuoso_web", "virtuoso_web")])
    icons_dir = Path("assets/icons")
    if icons_dir.exists():
        cmd.extend(["--add-data", get_data_arg("assets/icons", "assets/icons")])

    print("Building standalone executable with PyInstaller...")
    print(" ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print("PyInstaller build failed.")
    else:
        print(f"Build completed. Executable is available in {dist_dir}")
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Virtuoso standalone executable.")
    parser.add_argument(
        "--icon",
        type=str,
        default=None,
        help="Optional icon file to embed in the standalone executable.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Config YAML to bundle (default: virtuoso.yaml.example).",
    )
    args = parser.parse_args()

    entry_script = Path(__file__).parent.parent / "run_virtuoso.py"
    if not entry_script.exists():
        print("run_virtuoso.py not found in project root.")
        return 1

    cfg = Path(args.config) if args.config else None
    return build(entry_script, icon_path=args.icon, config_path=cfg)


if __name__ == "__main__":
    raise SystemExit(main())
