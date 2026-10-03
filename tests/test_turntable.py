"""Tests for the add-in's turntable helpers (pure Python, no Fusion)."""

import importlib.util
import math
import os
import subprocess

import pytest

_PATH = os.path.join(os.path.dirname(__file__), "..", "addon", "server",
                     "turntable.py")
# Load the file directly: importing the add-in package would pull in adsk.
_spec = importlib.util.spec_from_file_location("turntable", _PATH)
turntable = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(turntable)


def _close(a, b):
    return all(math.isclose(x, y, abs_tol=1e-9) for x, y in zip(a, b))


class TestOrbitAngles:
    def test_full_turn_has_no_duplicate_end_frame(self):
        angles = turntable.orbit_angles(4, 360)
        assert [round(math.degrees(a)) for a in angles] == [0, 90, 180, 270]

    def test_partial_turn_includes_both_ends(self):
        angles = turntable.orbit_angles(3, 90)
        assert [round(math.degrees(a)) for a in angles] == [0, 45, 90]

    def test_negative_full_turn(self):
        angles = turntable.orbit_angles(4, -360)
        assert round(math.degrees(angles[1])) == -90

    def test_rejects_too_few_frames(self):
        with pytest.raises(ValueError):
            turntable.orbit_angles(1, 360)

    def test_rejects_zero_degrees(self):
        with pytest.raises(ValueError):
            turntable.orbit_angles(10, 0)


class TestRotateAboutAxis:
    def test_quarter_turn_about_z(self):
        p = turntable.rotate_about_axis((1, 0, 0), (0, 0, 0), (0, 0, 1),
                                        math.pi / 2)
        assert _close(p, (0, 1, 0))

    def test_offset_origin_and_unnormalised_axis(self):
        p = turntable.rotate_about_axis((3, 2, 5), (2, 2, 5), (0, 0, 7),
                                        math.pi)
        assert _close(p, (1, 2, 5))

    def test_point_on_axis_stays(self):
        p = turntable.rotate_about_axis((0, 0, 4), (0, 0, 0), (0, 0, 1), 1.0)
        assert _close(p, (0, 0, 4))

    def test_distance_to_target_preserved(self):
        eye, target = (10, 7, 3), (1, 1, 1)
        p = turntable.rotate_about_axis(eye, target, (0, 1, 0), 0.7)
        assert math.isclose(math.dist(p, target), math.dist(eye, target))

    def test_zero_axis_rejected(self):
        with pytest.raises(ValueError):
            turntable.rotate_about_axis((1, 0, 0), (0, 0, 0), (0, 0, 0), 1.0)


class TestFfmpeg:
    def test_explicit_path_must_exist(self, tmp_path):
        assert turntable.find_ffmpeg(str(tmp_path / "nope")) is None
        binary = tmp_path / "ffmpeg"
        binary.write_text("")
        assert turntable.find_ffmpeg(str(binary)) == str(binary)

    def test_falls_back_to_candidates(self, monkeypatch, tmp_path):
        binary = tmp_path / "ffmpeg"
        binary.write_text("")
        monkeypatch.setattr(turntable.shutil, "which", lambda _n: None)
        monkeypatch.setattr(turntable, "_FFMPEG_CANDIDATES",
                            ("/does/not/exist", str(binary)))
        assert turntable.find_ffmpeg() == str(binary)

    def test_mp4_args(self):
        args = turntable.ffmpeg_args("ffmpeg", "/f", 30, "mp4", "/o.mp4")
        assert args[:2] == ["ffmpeg", "-y"]
        assert args[args.index("-framerate") + 1] == "30"
        assert args[args.index("-i") + 1] == os.path.join(
            "/f", turntable.FRAME_PATTERN)
        assert "libx264" in args and "yuv420p" in args
        assert args[-1] == "/o.mp4"

    def test_gif_args(self):
        args = turntable.ffmpeg_args("ffmpeg", "/f", 12, "gif", "/o.gif")
        assert "paletteuse" in args[args.index("-vf") + 1]
        assert args[-1] == "/o.gif"

    def test_unknown_format(self):
        with pytest.raises(ValueError):
            turntable.ffmpeg_args("ffmpeg", "/f", 24, "avi", "/o.avi")

    def test_encode_raises_with_stderr(self, monkeypatch):
        def fake_run(*_a, **_kw):
            return subprocess.CompletedProcess([], 1, "", "boom")
        monkeypatch.setattr(turntable.subprocess, "run", fake_run)
        with pytest.raises(RuntimeError, match="boom"):
            turntable.encode(["ffmpeg"])
