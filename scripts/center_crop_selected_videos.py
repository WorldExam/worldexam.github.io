#!/usr/bin/env python3
"""Build center-cropped comparison videos from selected case directories."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
BASE_FPS = 24.0
TARGET_ASPECT = TARGET_WIDTH / TARGET_HEIGHT
HAPPYHORSE_EXTRA_ZOOM = 1.15


@dataclass(frozen=True)
class Clip:
    metric: str
    group: str
    label: str
    source_dir: Path
    input_path: Path
    input_kind: str
    natural_duration: float
    frame_count: int | None
    width: int
    height: int


def run_json(command: list[str]) -> dict:
    result = subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(result.stdout)


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Required tool not found: {name}")


def probe_media(media: Path) -> tuple[int, int, float | None]:
    data = run_json(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,duration",
            "-of",
            "json",
            str(media),
        ]
    )
    stream = data["streams"][0]
    duration = stream.get("duration")
    return int(stream["width"]), int(stream["height"]), float(duration) if duration else None


def probe_duration(media: Path) -> float:
    data = run_json(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(media),
        ]
    )
    return float(data["format"]["duration"])


def numbered_frames(frames_dir: Path) -> list[Path]:
    frames = sorted(frames_dir.glob("*.png"))
    if not frames:
        return []
    expected = [frames_dir / f"{i:03d}.png" for i in range(len(frames))]
    if frames != expected:
        raise ValueError(f"Frames must be contiguous 000.png sequence: {frames_dir}")
    return frames


def discover_clips(input_root: Path) -> list[Clip]:
    clips: list[Clip] = []
    for metric_dir in sorted(path for path in input_root.iterdir() if path.is_dir()):
        metric = metric_dir.name
        for group_dir in sorted(path for path in metric_dir.iterdir() if path.is_dir()):
            for clip_dir in sorted(path for path in group_dir.iterdir() if path.is_dir()):
                if not (clip_dir.name.startswith("good_") or clip_dir.name.startswith("bad_")):
                    continue
                frames_dir = clip_dir / "frames"
                frames = numbered_frames(frames_dir)
                if frames:
                    width, height, _ = probe_media(frames[0])
                    input_path = frames_dir
                    input_kind = "frames"
                    frame_count: int | None = len(frames)
                    natural_duration = len(frames) / BASE_FPS
                else:
                    video = clip_dir / "video.mp4"
                    if not video.exists():
                        continue
                    width, height, duration = probe_media(video)
                    input_path = video
                    input_kind = "video"
                    frame_count = None
                    natural_duration = duration if duration is not None else probe_duration(video)
                clips.append(
                    Clip(
                        metric=metric,
                        group=group_dir.name,
                        label=clip_dir.name,
                        source_dir=clip_dir,
                        input_path=input_path,
                        input_kind=input_kind,
                        natural_duration=natural_duration,
                        frame_count=frame_count,
                        width=width,
                        height=height,
                    )
                )
    return clips


def group_clips(clips: list[Clip]) -> dict[tuple[str, str], list[Clip]]:
    grouped: dict[tuple[str, str], list[Clip]] = {}
    for clip in clips:
        grouped.setdefault((clip.metric, clip.group), []).append(clip)
    return grouped


def even(value: int) -> int:
    return max(2, value - (value % 2))


def crop_filter(width: int, height: int, label: str) -> str:
    if width / height >= TARGET_ASPECT:
        crop_h = height
        crop_w = even(math.floor(height * TARGET_ASPECT))
    else:
        crop_w = width
        crop_h = even(math.floor(width / TARGET_ASPECT))

    if "happyhorse" in label.lower():
        crop_w = even(math.floor(crop_w / HAPPYHORSE_EXTRA_ZOOM))
        crop_h = even(math.floor(crop_h / HAPPYHORSE_EXTRA_ZOOM))

    x = even(math.floor((width - crop_w) / 2))
    y = even(math.floor((height - crop_h) / 2))
    return (
        f"crop={crop_w}:{crop_h}:{x}:{y},"
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:flags=lanczos,"
        "setsar=1,format=yuv420p"
    )


def output_path(output_root: Path, clip: Clip) -> Path:
    return output_root / clip.metric / clip.group / f"{clip.label}.mp4"


def build_clip(clip: Clip, output_file: Path, target_duration: float) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if clip.input_kind == "frames":
        assert clip.frame_count is not None
        fps = clip.frame_count / target_duration
        input_args = [
            "-framerate",
            f"{fps:.8f}",
            "-i",
            str(clip.input_path / "%03d.png"),
        ]
        filters = crop_filter(clip.width, clip.height, clip.label)
    else:
        input_args = ["-i", str(clip.input_path)]
        speed = target_duration / clip.natural_duration
        filters = f"{crop_filter(clip.width, clip.height, clip.label)},setpts={speed:.12f}*PTS"

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        *input_args,
        "-vf",
        filters,
        "-r",
        f"{BASE_FPS:g}",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        "-an",
        str(output_file),
    ]
    subprocess.run(command, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("video") / "剩余",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("video") / "selected_object_social_interaction_videos_center_cropped",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned outputs without writing mp4 files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require_tool("ffmpeg")
    require_tool("ffprobe")

    clips = discover_clips(args.input_root)
    grouped = group_clips(clips)
    if not grouped:
        raise SystemExit(f"No selected case videos found under {args.input_root}")

    for key, pair in sorted(grouped.items()):
        if len(pair) != 2:
            labels = ", ".join(clip.label for clip in pair)
            raise SystemExit(f"Expected 2 clips in {key}, found {len(pair)}: {labels}")

    for (metric, group), pair in sorted(grouped.items()):
        target_duration = max(clip.natural_duration for clip in pair)
        print(f"{metric}/{group}: target_duration={target_duration:.3f}s")
        for clip in sorted(pair, key=lambda item: item.label):
            out = output_path(args.output_root, clip)
            if clip.input_kind == "frames":
                assert clip.frame_count is not None
                timing = f"frames={clip.frame_count} fps={clip.frame_count / target_duration:.4f}"
            else:
                timing = (
                    f"video_duration={clip.natural_duration:.3f}s "
                    f"setpts={target_duration / clip.natural_duration:.4f}"
                )
            print(f"  {clip.label}: {timing} size={clip.width}x{clip.height} -> {out}")
            if not args.dry_run:
                build_clip(clip, out, target_duration)


if __name__ == "__main__":
    main()
