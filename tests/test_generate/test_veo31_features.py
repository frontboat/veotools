"""Tests for Veo 3.1 helper generation flows."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from veotools.generate.video import (
    extend_video,
    generate_with_interpolation,
    generate_with_reference_images,
)


def _fake_client(video_bytes: bytes = b"video"):
    video = SimpleNamespace(data=video_bytes)
    done_operation = SimpleNamespace(
        done=True,
        response=SimpleNamespace(generated_videos=[SimpleNamespace(video=video)]),
    )
    operation = SimpleNamespace(done=False, name="op-1", response=None, error=None)
    return SimpleNamespace(
        models=SimpleNamespace(generate_videos=Mock(return_value=operation)),
        operations=SimpleNamespace(get=Mock(return_value=done_operation)),
    )


def _setup_generation_mocks(monkeypatch, tmp_path):
    monkeypatch.setenv("VEO_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr("veotools.generate.video.time.sleep", lambda _: None)
    monkeypatch.setattr(
        "veotools.generate.video.get_video_info",
        lambda _: {"fps": 24, "duration": 8, "width": 1280, "height": 720},
    )


def test_generate_with_reference_images_defaults_person_generation(monkeypatch, tmp_path):
    _setup_generation_mocks(monkeypatch, tmp_path)
    fake_client = _fake_client()
    monkeypatch.setattr(
        "veotools.generate.video.VeoClient",
        lambda: SimpleNamespace(provider="google", client=fake_client),
    )

    captured = {}

    def fake_build(model, **kwargs):
        captured["model"] = model
        captured["kwargs"] = kwargs
        return "CONFIG"

    monkeypatch.setattr(
        "veotools.generate.video.ModelConfig.build_generation_config",
        fake_build,
    )
    monkeypatch.setattr(
        "veotools.generate.video.types.Image.from_file",
        lambda location: SimpleNamespace(source=location),
    )

    ref1 = tmp_path / "ref1.png"
    ref2 = tmp_path / "ref2.png"
    ref1.write_bytes(b"ref1")
    ref2.write_bytes(b"ref2")

    result = generate_with_reference_images(
        prompt="A character walking",
        reference_images=[str(ref1), str(ref2)],
        model="veo-3.1-generate-preview",
    )

    assert captured["kwargs"]["person_generation"] == "allow_adult"
    assert len(captured["kwargs"]["reference_images"]) == 2
    assert captured["kwargs"]["reference_images"][0].source.endswith("ref1.png")
    assert result.path and Path(result.path).exists()


def test_generate_with_interpolation_includes_last_frame(monkeypatch, tmp_path):
    _setup_generation_mocks(monkeypatch, tmp_path)
    fake_client = _fake_client()
    monkeypatch.setattr(
        "veotools.generate.video.VeoClient",
        lambda: SimpleNamespace(provider="google", client=fake_client),
    )

    captured = {}

    def fake_build(model, **kwargs):
        captured["kwargs"] = kwargs
        return "CONFIG"

    monkeypatch.setattr(
        "veotools.generate.video.ModelConfig.build_generation_config",
        fake_build,
    )
    monkeypatch.setattr(
        "veotools.generate.video.types.Image.from_file",
        lambda location: SimpleNamespace(source=location),
    )

    first_frame = tmp_path / "first.jpg"
    last_frame = tmp_path / "last.jpg"
    first_frame.write_bytes(b"first")
    last_frame.write_bytes(b"last")

    result = generate_with_interpolation(
        first_frame=first_frame,
        last_frame=last_frame,
        prompt="Smooth transition",
        model="veo-3.1-generate-preview",
    )

    assert captured["kwargs"]["person_generation"] == "allow_adult"
    assert captured["kwargs"]["last_frame"].source.endswith("last.jpg")
    assert result.path and Path(result.path).exists()


def test_extend_video_defaults_person_generation_allow_all(monkeypatch, tmp_path):
    _setup_generation_mocks(monkeypatch, tmp_path)
    fake_client = _fake_client()
    monkeypatch.setattr(
        "veotools.generate.video.VeoClient",
        lambda: SimpleNamespace(provider="google", client=fake_client),
    )
    monkeypatch.setattr(
        "veotools.generate.video.types.Video.from_file",
        lambda location: SimpleNamespace(source=location),
    )

    captured = {}

    def fake_build(model, **kwargs):
        captured["kwargs"] = kwargs
        return "CONFIG"

    monkeypatch.setattr(
        "veotools.generate.video.ModelConfig.build_generation_config",
        fake_build,
    )

    input_video = tmp_path / "input.mp4"
    input_video.write_bytes(b"video")

    result = extend_video(
        video_path=input_video,
        prompt="Continue the scene",
        model="veo-3.1-generate-preview",
    )

    assert captured["kwargs"]["person_generation"] == "allow_all"
    assert result.path and Path(result.path).exists()
