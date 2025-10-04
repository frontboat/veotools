"""API tests for plan_scenes wrapper."""

from __future__ import annotations

from veotools.api import mcp_api
from veotools.plan.scene_writer import (
    ScenePlan,
    Clip,
    Shot,
    Subject,
    Scene,
    VisualDetails,
    Cinematography,
    AudioTrack,
    Dialogue,
    Performance,
    CharacterProfile,
)


def _make_plan() -> ScenePlan:
    character = CharacterProfile(
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
    clip = Clip(
        id="clip-1",
        shot=Shot(
            composition="Medium close-up",
            camera="handheld",
            camera_motion="slow dolly-in",
            frame_rate="24 fps",
            film_grain=0.05,
        ),
        subject=Subject(
            description="Nyx stands at the pool edge",
            wardrobe="default outfit",
        ),
        scene=Scene(
            location="rooftop infinity pool",
            time_of_day="golden hour",
            environment="Sunlit water reflecting neon city lights",
        ),
        visual_details=VisualDetails(
            action="Nyx fans her hand toward the camera",
            props="Floating dollar-sign inflatables",
        ),
        cinematography=Cinematography(
            lighting="High-key golden sunlight",
            tone="Vibrant, playful, confident",
            color_grade="Hyper-saturated neon tropic",
        ),
        audio_track=AudioTrack(
            lyrics="Splash-cash, bling-blap",
            emotion="confident",
            flow="syncopated",
            format="wav",
            sample_rate_hz=48000,
            channels=2,
        ),
        dialogue=Dialogue(
            character="Nyx Cipher",
            line="Splash-cash, bling-blap—pool water pshh!",
            subtitles=False,
        ),
        performance=Performance(
            mouth_shape_intensity=0.7,
            eye_contact_ratio=0.5,
        ),
        duration_sec=8,
        aspect_ratio="16:9",
    )
    return ScenePlan(characters=[character], clips=[clip])


def test_plan_scenes_success(monkeypatch):
    monkeypatch.setattr(
        mcp_api,
        "generate_scene_plan",
        lambda *args, **kwargs: _make_plan(),
    )

    result = mcp_api.plan_scenes(idea="Luxury vlog", number_of_scenes=2)
    assert result["clips"][0]["id"] == "clip-1"
    assert result["characters"][0]["name"] == "Nyx Cipher"


def test_plan_scenes_validation_error(monkeypatch):
    def raise_value_error(*args, **kwargs):
        raise ValueError("bad input")

    monkeypatch.setattr(mcp_api, "generate_scene_plan", raise_value_error)

    result = mcp_api.plan_scenes(idea="bad")
    assert result["error_code"] == "VALIDATION"


def test_plan_scenes_unknown_error(monkeypatch):
    def raise_runtime_error(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(mcp_api, "generate_scene_plan", raise_runtime_error)

    result = mcp_api.plan_scenes(idea="boom")
    assert result["error_code"] == "UNKNOWN"
