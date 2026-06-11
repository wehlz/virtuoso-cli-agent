#!/usr/bin/env python3
"""Create a scripted fallback dashboard demo GIF."""

from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit("Install Pillow first: pip install Pillow") from exc


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "dashboard-scripted-demo.gif"
W, H = 960, 540


def font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


F_TITLE = font(26, True)
F_H2 = font(17, True)
F_BODY = font(14)
F_SMALL = font(12)
F_CODE = font(13)


def rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_gradient(img: Image.Image):
    px = img.load()
    left = (15, 23, 42)
    mid = (17, 94, 89)
    right = (124, 45, 18)
    for y in range(H):
        for x in range(W):
            t = (x / max(1, W - 1) + y / max(1, H - 1)) / 2
            if t < 0.55:
                u = t / 0.55
                color = tuple(int(left[i] * (1 - u) + mid[i] * u) for i in range(3))
            else:
                u = (t - 0.55) / 0.45
                color = tuple(int(mid[i] * (1 - u) + right[i] * u) for i in range(3))
            px[x, y] = color


def type_text(text: str, frame: int, start: int, speed: int = 2) -> str:
    if frame < start:
        return ""
    count = min(len(text), (frame - start) // speed)
    return text[:count]


def stage(frame: int) -> str:
    if frame < 14:
        return "setup"
    if frame < 45:
        return "typing"
    if frame < 62:
        return "running"
    return "done"


def frame_image(frame: int) -> Image.Image:
    img = Image.new("RGB", (W, H), "#0f172a")
    draw_gradient(img)
    d = ImageDraw.Draw(img)

    # Browser shell
    rounded(d, (54, 42, 906, 500), 18, "#e5e7eb")
    rounded(d, (54, 42, 906, 84), 18, "#f8fafc")
    d.rectangle((54, 66, 906, 84), fill="#f8fafc")
    for i, color in enumerate(("#ef4444", "#f59e0b", "#10b981")):
        d.ellipse((78 + i * 22, 58, 90 + i * 22, 70), fill=color)
    rounded(d, (160, 55, 730, 74), 9, "#e2e8f0")
    d.text((178, 58), "http://127.0.0.1:8788", fill="#334155", font=F_SMALL)

    # App background
    rounded(d, (78, 104, 882, 478), 14, "#0f172a")
    d.rectangle((78, 104, 882, 160), fill="#111827")
    d.text((104, 122), "Virtuoso", fill="#f8fafc", font=F_TITLE)
    d.text((240, 131), "AI coding agent for ordinary laptops", fill="#94a3b8", font=F_BODY)

    connected = frame >= 12
    badge_color = "#064e3b" if connected else "#78350f"
    badge_text = "Connected" if connected else "Setup"
    rounded(d, (742, 123, 846, 148), 12, badge_color)
    d.text((765 if connected else 778, 128), badge_text, fill="#d1fae5" if connected else "#fde68a", font=F_SMALL)

    # Setup panel
    rounded(d, (104, 184, 334, 444), 10, "#1f2937")
    d.text((126, 207), "Setup", fill="#f8fafc", font=F_H2)
    d.text((126, 244), "Provider", fill="#cbd5e1", font=F_SMALL)
    rounded(d, (126, 261, 308, 294), 8, "#0f172a")
    d.text((140, 270), "Gemini API Key", fill="#f8fafc", font=F_BODY)
    d.text((126, 323), "Status", fill="#cbd5e1", font=F_SMALL)
    rounded(d, (126, 340, 308, 395), 8, "#0f172a")
    d.text((140, 354), "Backend: gemini", fill="#e2e8f0", font=F_SMALL)
    d.text((140, 375), "Model: 2.5 Flash", fill="#e2e8f0", font=F_SMALL)

    # Work panel
    rounded(d, (362, 184, 856, 444), 10, "#020617")
    st = stage(frame)
    d.text((388, 207), "Build", fill="#f8fafc", font=F_H2)
    rounded(d, (388, 239, 830, 300), 8, "#111827")
    prompt = "make a Python todo app on my desktop titled todo"
    typed = type_text(prompt, frame, 18, speed=1)
    cursor = "|" if st == "typing" and frame % 6 < 3 else ""
    d.text((406, 260), typed + cursor, fill="#cbd5e1", font=F_BODY)

    run_color = "#0f766e" if st in ("typing", "setup") else "#134e4a"
    rounded(d, (388, 322, 486, 357), 8, run_color)
    d.text((421, 332), "Run", fill="#ccfbf1", font=F_BODY)
    rounded(d, (502, 322, 600, 357), 8, "#1e293b")
    d.text((534, 332), "Plan", fill="#e2e8f0", font=F_BODY)

    rounded(d, (388, 377, 830, 422), 8, "#0f172a")
    if st == "setup":
        d.text((406, 391), "Paste a key once, then build from the dashboard.", fill="#93c5fd", font=F_CODE)
    elif st == "typing":
        d.text((406, 391), "Ready: choose a mode and enter a prompt.", fill="#93c5fd", font=F_CODE)
    elif st == "running":
        dots = "." * ((frame // 4) % 4)
        d.text((406, 391), f"Building todo.py{dots}", fill="#fde68a", font=F_CODE)
        progress = min(1.0, (frame - 45) / 17)
        rounded(d, (610, 394, 800, 405), 5, "#1f2937")
        rounded(d, (610, 394, 610 + int(190 * progress), 405), 5, "#14b8a6")
    else:
        d.text((406, 391), r"Saved to: C:\Users\you\Desktop\todo.py", fill="#93c5fd", font=F_CODE)
        d.text((406, 413), "Review Result: PASS", fill="#a7f3d0", font=F_CODE)

    # Footer caption
    captions = {
        "setup": "Connect Gemini or an OpenAI-compatible provider",
        "typing": "Describe what you want to build",
        "running": "Virtuoso plans, generates, reviews, and saves",
        "done": "Generated code lands where you asked for it",
    }
    d.text((78, 512), captions[st], fill="#f8fafc", font=F_BODY)
    return img


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames = [frame_image(i) for i in range(78)]
    durations = [70] * len(frames)
    durations[-1] = 1400
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
