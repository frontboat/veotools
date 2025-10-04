"""Tests for the Gemini-powered scene writer helpers."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from veotools.plan.scene_writer import (
    CharacterProfile,
    ScenePlan,
    SceneWriter,
    generate_scene_plan,
)


def _sample_plan_payload() -> dict:
    return {
        "characters": [
            {
                "name": "Nyx Cipher",
                "age": 27,
                "height": "5'8\" / 173 cm",
                "build": "lean, athletic",
                "skin_tone": "deep bronze",
                "hair": "jet-black bob",
                "eyes": "hazel",
                "distinguishing_marks": "star tattoo behind right ear",
                "demeanour": "playfully self-assured",
                "default_outfit": "metallic coral bikini, mirrored sunglasses, gold hoop earrings",
                "mouth_shape_intensity": 0.8,
                "eye_contact_ratio": 0.6,
            }
        ],
        "clips": [
            {
                "id": "clip-1",
                "shot": {
                    "composition": "Medium close-up, 35mm lens",
                    "camera": "handheld mirrorless",
                    "camera_motion": "slow dolly-in",
                    "frame_rate": "24 fps",
                    "film_grain": 0.05,
                },
                "subject": {
                    "description": "Nyx glistening in the neon sunset",
                    "wardrobe": "default outfit",
                },
                "scene": {
                    "location": "rooftop infinity pool",
                    "time_of_day": "golden hour",
                    "environment": "Sunlit pool water reflecting shifting neon patterns",
                },
                "visual_details": {
                    "action": "Nyx leans on the pool edge and fans her hand toward camera",
                    "props": "Floating dollar-sign inflatables",
                },
                "cinematography": {
                    "lighting": "High-key golden sunlight with prism flares",
                    "tone": "Vibrant, playful, confident",
                    "color_grade": "Hyper-saturated neon tropic",
                },
                "audio_track": {
                    "lyrics": "Splash-cash, bling-blap",
                    "emotion": "confident",
                    "flow": "syncopated",
                    "format": "wav",
                    "sample_rate_hz": 48000,
                    "channels": 2,
                },
                "dialogue": {
                    "character": "Nyx Cipher",
                    "line": "Splash-cash, bling-blap—pool water pshh!",
                    "subtitles": False,
                },
                "performance": {
                    "mouth_shape_intensity": 0.7,
                    "eye_contact_ratio": 0.5,
                },
                "duration_sec": 8,
                "aspect_ratio": "16:9",
            }
        ],
    }


def _patch_client(monkeypatch, capture):
    def fake_generate_content(*, model, contents, config):
        capture["model"] = model
        capture["contents"] = contents
        capture["config"] = config
        return SimpleNamespace(text=json.dumps(_sample_plan_payload()))

    fake_models = SimpleNamespace(generate_content=fake_generate_content)
    fake_client = SimpleNamespace(models=fake_models)
    monkeypatch.setattr(
        "veotools.plan.scene_writer.VeoClient",
        lambda: SimpleNamespace(client=fake_client),
    )


def test_generate_scene_plan_writes_file(monkeypatch, tmp_path):
    capture: dict = {}
    _patch_client(monkeypatch, capture)

    plan = generate_scene_plan(
        "A slick rooftop vlog about a luxury energy drink.",
        number_of_scenes=1,
        save_path=tmp_path / "plan.json",
    )

    assert isinstance(plan, ScenePlan)
    assert plan.clips[0].id == "clip-1"
    assert capture["model"] == "gemini-2.5-pro"
    assert "luxury energy drink" in capture["contents"]
    saved = (tmp_path / "plan.json").read_text(encoding="utf-8")
    assert "clip-1" in saved


def test_scene_writer_includes_character_context(monkeypatch):
    capture: dict = {}
    _patch_client(monkeypatch, capture)

    reference = CharacterProfile(
        name="Nyx Cipher",
        age=27,
        height="5'8\" / 173 cm",
        build="lean",
        skin_tone="bronze",
        hair="jet-black",
        eyes="hazel",
        distinguishing_marks="tiny star tattoo",
        demeanour="playfully self-assured",
        default_outfit="metallic-coral bikini",
        mouth_shape_intensity=0.8,
        eye_contact_ratio=0.6,
    )

    writer = SceneWriter()
    plan = writer.generate(
        "Poolside brag vlog",
        number_of_scenes=1,
        additional_context="Keep it upbeat and short.",
        character_references=[reference],
        character_description="Nyx Cipher — 27-year-old influencer with neon streetwear flair",
        character_characteristics="playfully self-assured, confident",
        video_type="vlog",
        video_characteristics="bright, high-definition, comedic",
        camera_angle="front, close-up",
    )

    assert plan.characters[0].name == "Nyx Cipher"
    prompt = capture["contents"]
    assert "Character References" in prompt
    assert "Keep it upbeat" in prompt


@pytest.mark.parametrize("empty_response", [None, ""])
def test_scene_writer_raises_on_empty_response(monkeypatch, empty_response):
    def fake_generate_content(*, model, contents, config):
        return SimpleNamespace(text=empty_response)

    fake_models = SimpleNamespace(generate_content=fake_generate_content)
    fake_client = SimpleNamespace(models=fake_models)
    monkeypatch.setattr(
        "veotools.plan.scene_writer.VeoClient",
        lambda: SimpleNamespace(client=fake_client),
    )

    writer = SceneWriter()
    with pytest.raises(RuntimeError):
        writer.generate("Empty response", number_of_scenes=1)


def test_scene_writer_daydreams_strips_code_fence(monkeypatch):
    payload = {
        "choices": [
            {
                "message": {
                    "content": "```json\n{\n  \"characters\": [],\n  \"clips\": []\n}\n```"
                }
            }
        ]
    }

    client = Mock()
    client.create_chat_completion.return_value = payload
    wrapper = SimpleNamespace(provider="daydreams", client=client)
    monkeypatch.setattr("veotools.plan.scene_writer.VeoClient", lambda: wrapper)

    writer = SceneWriter()
    plan = writer.generate("Neon skyline", number_of_scenes=1)

    assert plan.characters == []
    assert plan.clips == []
