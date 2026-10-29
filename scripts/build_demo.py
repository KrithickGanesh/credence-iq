"""Assemble the demo video and its thumbnail from the Playwright recording.

Inputs are reproducible artifacts: the title/end cards rendered by
``render_demo_cards.py`` and the raw WebM + trim metadata written by
``record_demo.py``. The output is an H.264 MP4 suitable for GitHub.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "docs" / "demo"
RAW = DEMO / "raw"
VIDEO = DEMO / "credenceiq-demo.mp4"
THUMBNAIL = DEMO / "thumbnail.png"
SCREENSHOT = ROOT / "docs" / "screenshots" / "overview.png"


def build_video() -> None:
    meta = json.loads((RAW / "recording.json").read_text(encoding="utf-8"))
    trim = float(meta["trim_seconds"])
    duration = float(meta["recording_seconds"]) - trim
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-loop",
        "1",
        "-framerate",
        "30",
        "-t",
        "4",
        "-i",
        str(DEMO / "title.png"),
        "-ss",
        f"{trim:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(RAW / "credenceiq-demo.webm"),
        "-loop",
        "1",
        "-framerate",
        "30",
        "-t",
        "6",
        "-i",
        str(DEMO / "end.png"),
        "-filter_complex",
        (
            "[0:v]fps=30,scale=1440:810,setsar=1,format=yuv420p[v0];"
            "[1:v]fps=30,scale=1440:810,setsar=1,format=yuv420p[v1];"
            "[2:v]fps=30,scale=1440:810,setsar=1,format=yuv420p[v2];"
            "[v0][v1][v2]concat=n=3:v=1:a=0[outv]"
        ),
        "-map",
        "[outv]",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-r",
        "30",
        str(VIDEO),
    ]
    subprocess.run(command, check=True)
    print(f"wrote {VIDEO} ({VIDEO.stat().st_size / 1_000_000:.1f} MB, {duration + 10:.1f}s)")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path(r"C:\Windows\Fonts\seguisb.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def build_thumbnail() -> None:
    with Image.open(SCREENSHOT) as source:
        image = source.convert("RGB").crop((0, 0, 1440, 810))

    # Darken the dashboard slightly so the play control and caption read clearly.
    image = Image.alpha_composite(image.convert("RGBA"), Image.new("RGBA", image.size, (7, 18, 15, 56)))
    draw = ImageDraw.Draw(image, "RGBA")

    # Bottom caption band.
    for offset in range(190):
        alpha = int(180 * (offset / 189) ** 0.8)
        draw.rectangle([0, 810 - 190 + offset, 1440, 810 - 190 + offset + 1], fill=(7, 18, 15, alpha))

    # Play control with a soft shadow.
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse([720 - 62, 380 - 62, 720 + 62, 380 + 62], fill=(0, 0, 0, 120))
    image = Image.alpha_composite(image, shadow.filter(ImageFilter.GaussianBlur(18)))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.ellipse([720 - 56, 380 - 56, 720 + 56, 380 + 56], fill=(20, 134, 106, 245), outline=(255, 255, 255, 235), width=4)
    draw.polygon([(705, 356), (705, 404), (744, 380)], fill=(255, 255, 255, 255))

    title_font = font(34, bold=True)
    subtitle_font = font(18)
    draw.text((64, 664), "Watch the 71-second demo", font=title_font, fill=(248, 250, 252, 255))
    draw.text(
        (64, 710),
        "Exasol-native scoring, cross-ledger reconciliation, and adverse-action drafting",
        font=subtitle_font,
        fill=(203, 213, 225, 255),
    )
    draw.text((64, 746), "github.com/KrithickGanesh/credence-iq", font=font(14), fill=(148, 163, 184, 255))

    image.convert("RGB").save(THUMBNAIL, optimize=True)
    print(f"wrote {THUMBNAIL}")


def main() -> None:
    build_video()
    build_thumbnail()


if __name__ == "__main__":
    main()
