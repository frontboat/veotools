"""Tests for executing scene plans into rendered videos."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from veotools.models import VideoResult
from veotools.plan.executor import execute_scene_plan, PlanExecutionResult


def _make_plan_dict() -> dict:
    return {
        "characters": [
            {
                "name": "Nyx Cipher",
                "age": 27,
                "height": "5'8\" / 173 cm",
                "build": "lean",
                "skin_tone": "bronze",
                "hair": "jet-black",
                "eyes": "hazel",
                "demeanour": "playful",
                "default_outfit": "bikini",
                "mouth_shape_intensity": 0.8,
                "eye_contact_ratio": 0.6,
            }
        ],
        "clips": [
            {
                "id": "clip_001",
                "shot": {
                    "composition": "Medium close-up",
                    "camera_motion": "slow push-in",
                    "frame_rate": "24 fps",
                    "film_grain": 0.05,
                    "camera": "handheld",
                },
                "subject": {
                    "description": "Nyx explains the concept",
                    "wardrobe": "retro tech outfit",
                },
                "scene": {
                    "location": "Virtual neon lab",
                    "time_of_day": "night",
                    "environment": "Holographic schematics floating around",
                },
                "visual_details": {
                    "action": "Nyx gestures to floating diagrams",
                    "props": "Holographic controller",
                },
                "cinematography": {
                    "lighting": "Cool neon rim light",
                    "tone": "Excited instructional",
                    "color_grade": "Retro teal and magenta",
                },
                "audio_track": {
                    "lyrics": None,
                    "emotion": "confident",
                    "flow": None,
                    "format": "wav",
                    "sample_rate_hz": 48000,
                    "channels": 2,
                    "style": None,
                },
                "dialogue": {
                    "character": "Nyx",
                    "line": "Let me show you how x402 keeps stablecoins safe!",
                    "subtitles": False,
                },
                "performance": {
                    "mouth_shape_intensity": 0.7,
                    "eye_contact_ratio": 0.6,
                },
                "duration_sec": 8,
                "aspect_ratio": "16:9",
            },
            {
                "id": "clip_002",
                "shot": {
                    "composition": "Wide shot",
                    "camera_motion": "orbit",
                    "frame_rate": "24 fps",
                    "film_grain": 0.05,
                    "camera": "virtual crane",
                },
                "subject": {
                    "description": "A giant retro arcade cabinet shows protocol flow",
                    "wardrobe": "Same outfit",
                },
                "scene": {
                    "location": "Arcade skyline",
                    "time_of_day": "dawn",
                    "environment": "Pixel clouds and skyline",
                },
                "visual_details": {
                    "action": "Cabinet animates stablecoin transactions",
                    "props": "Arcade joystick",
                },
                "cinematography": {
                    "lighting": "Soft sunrise glow",
                    "tone": "Awe inspiring",
                    "color_grade": "Warm vintage palette",
                },
                "audio_track": {
                    "lyrics": None,
                    "emotion": None,
                    "flow": None,
                    "format": "wav",
                    "sample_rate_hz": 48000,
                    "channels": 2,
                    "style": None,
                },
                "dialogue": {
                    "character": "Narrator",
                    "line": "Automatic rebalancing keeps volatility in check.",
                    "subtitles": False,
                },
                "performance": {
                    "mouth_shape_intensity": 0.5,
                    "eye_contact_ratio": 0.4,
                },
                "duration_sec": 8,
                "aspect_ratio": "16:9",
            },
        ],
    }


def test_execute_scene_plan_generates_and_stitches(monkeypatch, tmp_path):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_make_plan_dict()), encoding="utf-8")

    prompts: list[str] = []
    called_kwargs: list[dict] = []

    def fake_generate_from_text(prompt, *, model, on_progress=None, **kwargs):
        prompts.append(prompt)
        called_kwargs.append({"model": model, **kwargs})
        result = VideoResult()
        result.path = tmp_path / f"clip_{len(prompts)}.mp4"
        return result

    stitched_paths: list[List[Path]] = []

    def fake_stitch(video_paths, overlap=1.0, on_progress=None):
        stitched_paths.append(video_paths)
        result = VideoResult()
        result.path = tmp_path / "final.mp4"
        return result

    monkeypatch.setattr(
        "veotools.plan.executor.generate_from_text", fake_generate_from_text
    )
    monkeypatch.setattr(
        "veotools.plan.executor.generate_from_image",
        lambda *a, **k: pytest.fail("generate_from_image should not be used"),
    )
    monkeypatch.setattr(
        "veotools.plan.executor.stitch_videos",
        fake_stitch,
    )

    result = execute_scene_plan(plan_path, model="veo-3.0-generate-001")

    assert isinstance(result, PlanExecutionResult)
    assert len(result.clip_results) == 2
    assert len(prompts) == 2
    assert called_kwargs[0]["aspect_ratio"] == "16:9"
    assert stitched_paths and len(stitched_paths[0]) == 2
    assert result.final_result is not None
    assert result.final_result.path.name == "final.mp4"


def test_execute_scene_plan_with_image_provider(monkeypatch, tmp_path):
    plan = _make_plan_dict()

    def fake_generate_from_image(image_path, prompt, *, model, on_progress=None, **kwargs):
        assert image_path == tmp_path / "seed.png"
        res = VideoResult()
        res.path = tmp_path / f"clip_image.mp4"
        return res

    monkeypatch.setattr(
        "veotools.plan.executor.generate_from_image",
        fake_generate_from_image,
    )
    monkeypatch.setattr(
        "veotools.plan.executor.generate_from_text",
        lambda *a, **k: pytest.fail("Expected image-based generation"),
    )
    monkeypatch.setattr(
        "veotools.plan.executor.stitch_videos",
        lambda video_paths, overlap=1.0, on_progress=None: VideoResult(),
    )

    image_provider = lambda clip, idx, plan: tmp_path / "seed.png"

    result = execute_scene_plan(
        plan,
        model="veo-3.0-generate-001",
        image_provider=image_provider,
        stitch=False,
    )

    # No stitching when disabled
    assert result.final_result is None
    assert len(result.clip_results) == 2


def test_execute_scene_plan_auto_seed_last_frame(monkeypatch, tmp_path):
    plan = _make_plan_dict()

    text_calls: list[Path] = []

    def fake_generate_from_text(prompt, *, model, on_progress=None, **kwargs):
        if text_calls:
            pytest.fail("generate_from_text should only run for the first clip when auto seeding")
        result = VideoResult()
        result.path = tmp_path / "clip_1.mp4"
        text_calls.append(result.path)
        return result

    seed_path = tmp_path / "seed_frame.png"
    extract_calls: list[tuple[Path, float]] = []

    def fake_extract_frame(video_path, time_offset):
        extract_calls.append((video_path, time_offset))
        return seed_path

    image_calls: list[Path] = []

    def fake_generate_from_image(image_path, prompt, *, model, on_progress=None, **kwargs):
        image_calls.append(image_path)
        result = VideoResult()
        result.path = tmp_path / "clip_2.mp4"
        return result

    monkeypatch.setattr(
        "veotools.plan.executor.generate_from_text",
        fake_generate_from_text,
    )
    monkeypatch.setattr(
        "veotools.plan.executor.generate_from_image",
        fake_generate_from_image,
    )
    monkeypatch.setattr(
        "veotools.plan.executor.extract_frame",
        fake_extract_frame,
    )
    monkeypatch.setattr(
        "veotools.plan.executor.stitch_videos",
        lambda video_paths, overlap=1.0, on_progress=None: VideoResult(),
    )

    result = execute_scene_plan(
        plan,
        auto_seed_last_frame=True,
        seed_frame_offset=-0.25,
    )

    assert len(text_calls) == 1
    assert image_calls == [seed_path]
    assert extract_calls == [(tmp_path / "clip_1.mp4", -0.25)]
    assert len(result.clip_results) == 2
