import json
import os
import platform
import shutil
import stat
import sys
from pathlib import Path
from typing import Optional

import requests

REPO_OWNER = "Michael-A-Kuykendall"
REPO_NAME = "shimmy"
REPO_SLUG = f"{REPO_OWNER}/{REPO_NAME}"
GITHUB_API_RELEASES = f"https://api.github.com/repos/{REPO_SLUG}/releases/latest"
GITHUB_RELEASES_PAGE = f"https://github.com/{REPO_SLUG}/releases/latest"


def _binary_name() -> str:
    return "shimmy.exe" if platform.system() == "Windows" else "shimmy"


def _platform_tags() -> tuple[str, str]:
    system = platform.system()
    arch = platform.machine().lower()
    if arch in ("amd64", "x86_64"):
        arch = "x86_64"
    elif arch in ("arm64", "aarch64"):
        arch = "aarch64"
    return system, arch


def _asset_score(asset_name: str, system: str, arch: str) -> int:
    asset_name = asset_name.lower()
    score = 0
    if system == "Windows":
        if asset_name.endswith(".exe"):
            score += 1
        if "windows" in asset_name:
            score += 4
        if arch in asset_name:
            score += 8
        if asset_name in ("shimmy.exe", "shimmy"):
            score += 2
    elif system == "Darwin":
        if asset_name.endswith(".tar.gz") or asset_name.endswith(".zip"):
            score += 1
        if "darwin" in asset_name or "macos" in asset_name:
            score += 4
        if arch in asset_name:
            score += 8
        if asset_name == "shimmy":
            score += 2
    elif system == "Linux":
        if asset_name.endswith(".tar.gz") or asset_name.endswith(".zip"):
            score += 1
        if "linux" in asset_name:
            score += 4
        if arch in asset_name:
            score += 8
        if asset_name == "shimmy":
            score += 2
    return score


def _find_asset(assets: list[dict], system: str, arch: str) -> dict:
    best_asset = None
    best_score = 0
    for asset in assets:
        name = asset.get("name", "")
        score = _asset_score(name, system, arch)
        if score > best_score:
            best_score = score
            best_asset = asset
    if best_asset is None or best_score == 0:
        raise RuntimeError(
            f"No Shimmy asset found for {system}/{arch}. Check {GITHUB_RELEASES_PAGE} for available downloads."
        )
    return best_asset


def _get_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _get_release_assets() -> list[dict]:
    resp = requests.get(GITHUB_API_RELEASES, headers=_get_headers(), timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Unable to fetch latest Shimmy release from GitHub ({resp.status_code})."
        )
    release = resp.json()
    assets = release.get("assets", [])
    if not assets:
        raise RuntimeError("No Shimmy release assets found in GitHub release metadata.")
    return assets


def _download_asset(download_url: str, destination: Path) -> Path:
    headers = _get_headers()
    headers["Accept"] = "application/octet-stream"
    with requests.get(download_url, headers=headers, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)
    return destination


def install_shimmy(target_dir: Path, force: bool = False) -> Path:
    """Download and install Shimmy into the target directory."""
    target_dir = target_dir.expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    binary_path = target_dir / _binary_name()
    if binary_path.exists() and not force:
        return binary_path
    if force and binary_path.exists():
        binary_path.unlink(missing_ok=True)

    system, arch = _platform_tags()
    assets = _get_release_assets()
    asset = _find_asset(assets, system, arch)
    asset_name = asset["name"]
    asset_url = asset["url"]
    archive_path = target_dir / asset_name

    _download_asset(asset_url, archive_path)

    if archive_path.suffix == ".zip" or archive_path.suffixes[-2:] == [".tar", ".gz"]:
        shutil.unpack_archive(str(archive_path), str(target_dir))
        archive_path.unlink(missing_ok=True)
    else:
        if binary_path.exists():
            binary_path.unlink()
        shutil.move(str(archive_path), str(binary_path))
        archive_path = binary_path

    if not binary_path.exists():
        candidates = list(target_dir.glob("**/" + _binary_name()))
        if candidates:
            binary_path = candidates[0]

    if not binary_path.exists():
        raise RuntimeError(
            "Shimmy binary was not found after extraction. Please inspect the downloaded release."
        )

    if platform.system() != "Windows":
        binary_path.chmod(binary_path.stat().st_mode | stat.S_IEXEC)
    return binary_path


def locate_shimmy(target_dir: Path) -> Optional[Path]:
    target_dir = target_dir.expanduser().resolve()
    candidates = [target_dir / _binary_name()]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Shimmy download helper for Virtuoso.")
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("./virtuoso_data/shimmy"),
        help="Directory where Shimmy should be installed.",
    )
    parser.add_argument("--force", action="store_true", help="Re-download Shimmy even if binary exists.")
    parser.add_argument("--dry-run", action="store_true", help="Show the intended download location without downloading.")
    args = parser.parse_args()

    if args.dry_run:
        print(f"Shimmy will install into: {args.target.resolve()}")
        return 0

    try:
        shimmy_path = install_shimmy(args.target, force=args.force)
        print(f"Shimmy installed at: {shimmy_path}")
        return 0
    except Exception as exc:
        print(f"Failed to install Shimmy: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
