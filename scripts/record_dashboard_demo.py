#!/usr/bin/env python3
"""Record the real dashboard UI into docs/assets/dashboard-demo.gif."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

try:
    from PIL import Image
except ImportError as exc:
    raise SystemExit("Install Pillow first: pip install Pillow") from exc


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "docs" / "assets" / "dashboard-demo.gif"
URL = "http://127.0.0.1:8788"


def wait_for_dashboard(timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{URL}/api/status", timeout=1):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def start_dashboard() -> subprocess.Popen[str]:
    cmd = [
        sys.executable,
        "-c",
        "from core.web_dashboard import run_dashboard; run_dashboard(open_browser=False)",
    ]
    return subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        text=True,
    )


def capture_frames(frame_dir: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Install recording dependencies first:\n"
            "  pip install playwright\n"
            "  python -m playwright install chromium"
        ) from exc

    frame_dir.mkdir(parents=True, exist_ok=True)
    counter = 1

    def frame(name: str) -> Path:
        nonlocal counter
        path = frame_dir / f"{counter:03d}-{name}.png"
        counter += 1
        return path

    def fulfill_json(route, payload: dict) -> None:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(payload),
        )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 760})

        page.route(
            "**/api/status",
            lambda route: fulfill_json(
                route,
                {
                    "connected": True,
                    "backend": "gemini",
                    "model": "gemini-2.5-flash",
                    "profile": "cloud",
                },
            ),
        )
        page.route("**/api/setup", lambda route: fulfill_json(route, {"ok": True}))

        def generate(route) -> None:
            time.sleep(0.65)
            fulfill_json(
                route,
                {
                    "text": "\n".join(
                        [
                            "Plan:",
                            "1. Create a small Python todo app.",
                            "2. Add save/load helpers.",
                            "3. Review the generated file.",
                            "",
                            "Review Result: PASS",
                        ]
                    ),
                    "saved_path": r"C:\Users\you\Desktop\todo.py",
                },
            )

        page.route("**/api/generate", generate)

        page.goto(URL, wait_until="networkidle")
        page.add_style_tag(
            content=(
                "* { transition-duration: 0s !important; "
                "animation-duration: 0s !important; } "
                "textarea { resize: none !important; }"
            )
        )
        page.wait_for_selector("#prompt")

        page.screenshot(path=str(frame("welcome")))
        page.fill("#api-key", "AIza************************")
        page.screenshot(path=str(frame("key-entered")))
        page.click("#save-key-btn")
        page.wait_for_timeout(300)
        page.screenshot(path=str(frame("connected")))

        page.click('[data-mode="build"]')
        page.wait_for_timeout(150)
        page.screenshot(path=str(frame("build-mode")))

        prompt = "make a Python todo app on my desktop titled todo"
        for i in range(8, len(prompt), 6):
            page.fill("#prompt", prompt[:i])
            page.screenshot(path=str(frame(f"typing-{i}")))
        page.fill("#prompt", prompt)
        page.screenshot(path=str(frame("prompt-ready")))

        page.click("#send-btn")
        page.wait_for_timeout(120)
        page.screenshot(path=str(frame("processing")))
        page.wait_for_selector(".msg.assistant")
        page.wait_for_timeout(200)
        page.screenshot(path=str(frame("done")))
        browser.close()


def make_gif(frame_dir: Path, output: Path) -> None:
    paths = sorted(p for p in frame_dir.glob("*.png") if p.is_file())
    if not paths:
        raise SystemExit("No dashboard frames were captured.")

    frames = []
    for path in paths:
        img = Image.open(path).convert("RGB")
        img.thumbnail((960, 608), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (960, 608), "#ffffff")
        x = (960 - img.width) // 2
        y = (608 - img.height) // 2
        canvas.paste(img, (x, y))
        frames.append(canvas)

    durations = [480] * len(frames)
    if len(durations) > 6:
        for i in range(4, len(durations) - 2):
            durations[i] = 95
    durations[-1] = 1600

    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--keep-frames",
        action="store_true",
        help="Keep the captured PNG frames for troubleshooting.",
    )
    args = parser.parse_args()

    dashboard = None
    if not wait_for_dashboard(timeout=1.5):
        dashboard = start_dashboard()
        if not wait_for_dashboard():
            if dashboard:
                dashboard.terminate()
            raise SystemExit("Dashboard did not start on http://127.0.0.1:8788")

    temp_root = Path(tempfile.mkdtemp(prefix="virtuoso-dashboard-gif-"))
    frame_dir = temp_root / "frames"
    try:
        capture_frames(frame_dir)
        make_gif(frame_dir, args.output)
        print(f"Wrote {args.output}")
        if args.keep_frames:
            print(f"Frames kept at {frame_dir}")
    finally:
        if dashboard:
            dashboard.terminate()
            try:
                dashboard.wait(timeout=5)
            except subprocess.TimeoutExpired:
                dashboard.kill()
        if not args.keep_frames:
            shutil.rmtree(temp_root, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
