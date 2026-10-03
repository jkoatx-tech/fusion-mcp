"""
Turntable helpers — orbit math and FFmpeg invocation.

Pure Python with no ``adsk`` import, so it can be unit-tested outside
Fusion. ``CommandHandler.capture_turntable`` drives the camera with it.
"""

import math
import os
import shutil
import subprocess
import sys

# GUI apps on macOS don't inherit the shell PATH, so Homebrew's ffmpeg
# is invisible to shutil.which inside Fusion.
_FFMPEG_CANDIDATES = (
    "/opt/homebrew/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/usr/bin/ffmpeg",
)

FRAME_PATTERN = "frame_%04d.png"


def orbit_angles(frames: int, degrees: float) -> list[float]:
    """Angles in radians for each frame.

    A full turn leaves out the end angle so the video loops without a
    duplicate frame; a partial turn includes both ends.
    """
    if frames < 2:
        raise ValueError("frames must be >= 2")
    if degrees == 0:
        raise ValueError("degrees must not be 0")
    full_turn = math.isclose(abs(degrees) % 360, 0) and degrees != 0
    steps = frames if full_turn else frames - 1
    return [math.radians(degrees * i / steps) for i in range(frames)]


def rotate_about_axis(point, origin, axis, angle: float) -> tuple:
    """Rotate *point* by *angle* (radians) about the line origin + t·axis.

    Rodrigues' rotation formula; all vectors are 3-sequences.
    """
    length = math.sqrt(sum(a * a for a in axis))
    if length == 0:
        raise ValueError("rotation axis has zero length")
    k = [a / length for a in axis]
    v = [p - o for p, o in zip(point, origin)]
    cos, sin = math.cos(angle), math.sin(angle)
    cross = (k[1] * v[2] - k[2] * v[1],
             k[2] * v[0] - k[0] * v[2],
             k[0] * v[1] - k[1] * v[0])
    dot = sum(a * b for a, b in zip(k, v))
    return tuple(
        o + v[i] * cos + cross[i] * sin + k[i] * dot * (1 - cos)
        for i, o in enumerate(origin)
    )


def find_ffmpeg(explicit: str | None = None) -> str | None:
    """Path to ffmpeg: *explicit*, then PATH, then common install dirs."""
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in _FFMPEG_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    return None


def ffmpeg_args(ffmpeg: str, frames_dir: str, fps: int, fmt: str,
                output: str) -> list[str]:
    """Command line that encodes the numbered PNGs in *frames_dir*."""
    pattern = os.path.join(frames_dir, FRAME_PATTERN)
    head = [ffmpeg, "-y", "-loglevel", "error",
            "-framerate", str(fps), "-i", pattern]
    if fmt == "mp4":
        # yuv420p needs even dimensions; pad by one pixel if necessary
        return head + [
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
            "-movflags", "+faststart", output,
        ]
    if fmt == "gif":
        return head + [
            "-vf", "split[a][b];[a]palettegen[p];[b][p]paletteuse",
            "-loop", "0", output,
        ]
    raise ValueError(f"Unknown video format '{fmt}' — use mp4 or gif")


def encode(args: list[str], timeout: float = 300) -> None:
    """Run ffmpeg; raise RuntimeError with its stderr on failure."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) \
        if sys.platform == "win32" else 0
    proc = subprocess.run(args, capture_output=True, text=True,
                          timeout=timeout, creationflags=flags)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed ({proc.returncode}): {proc.stderr.strip()}")
