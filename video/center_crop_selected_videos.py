#!/usr/bin/env python3
"""Center-crop selected videos to a common 16:9 output.

The happyhorse clip gets an additional centered zoom crop because its watermark
is near the lower-right corner.

  之后如果要重新生成，可以运行：

  python3 video/center_crop_selected_videos.py

  只看裁剪参数不转码：

  python3 video/center_crop_selected_videos.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "video" / "selected_object_social_interaction_videos"
DEFAULT_OUTPUT_DIR = ROOT / "video" / "selected_object_social_interaction_videos_center_cropped"

TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
TARGET_ASPECT = TARGET_WIDTH / TARGET_HEIGHT

# 1.18 crops to about 85% of the normal 16:9 crop before scaling back.
HAPPYHORSE_EXTRA_ZOOM = 1.18


def even_floor(value: float) -> int:
    return max(2, int(value) // 2 * 2)


def video_size(path: Path) -> tuple[int, int]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    streams = json.loads(result.stdout).get("streams", [])
    if not streams:
        raise RuntimeError(f"No video stream found: {path}")
    return int(streams[0]["width"]), int(streams[0]["height"])


def crop_box(width: int, height: int, extra_zoom: float = 1.0) -> tuple[int, int, int, int]:
    if width / height > TARGET_ASPECT:
        crop_h = even_floor(height)
        crop_w = even_floor(crop_h * TARGET_ASPECT)
    else:
        crop_w = even_floor(width)
        crop_h = even_floor(crop_w / TARGET_ASPECT)

    if extra_zoom != 1.0:
        crop_w = even_floor(crop_w / extra_zoom)
        crop_h = even_floor(crop_w / TARGET_ASPECT)
        if crop_h > height:
            crop_h = even_floor(height / extra_zoom)
            crop_w = even_floor(crop_h * TARGET_ASPECT)

    x = max(0, (width - crop_w) // 2)
    y = max(0, (height - crop_h) // 2)
    return crop_w, crop_h, x, y


def process_video(input_path: Path, output_path: Path, dry_run: bool) -> None:
    width, height = video_size(input_path)
    extra_zoom = HAPPYHORSE_EXTRA_ZOOM if "happyhorse" in input_path.name.lower() else 1.0
    crop_w, crop_h, x, y = crop_box(width, height, extra_zoom)

    vf = f"crop={crop_w}:{crop_h}:{x}:{y},scale={TARGET_WIDTH}:{TARGET_HEIGHT},setsar=1"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "medium",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    print(
        f"{input_path.name}: {width}x{height} -> crop {crop_w}x{crop_h}+{x}+{y} "
        f"-> {TARGET_WIDTH}x{TARGET_HEIGHT}"
    )
    if not dry_run:
        subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Print crop plans without encoding.")
    args = parser.parse_args()

    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise SystemExit("ffprobe and ffmpeg are required.")

    videos = sorted(args.input_dir.glob("*.mp4"))
    if not videos:
        raise SystemExit(f"No mp4 files found in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for input_path in videos:
        output_path = args.output_dir / input_path.name
        process_video(input_path, output_path, args.dry_run)


if __name__ == "__main__":
    main()
