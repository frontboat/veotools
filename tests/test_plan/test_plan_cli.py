"""CLI tests for the scene planning command."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from veotools import cli
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


def test_cmd_plan_json_output(monkeypatch, capsys):
    called = {}

    def fake_generate_scene_plan(*args, **kwargs):
        called.update(kwargs)
        return _make_plan()

    monkeypatch.setattr(cli.veo, "init", lambda: None)
    monkeypatch.setattr(cli.veo, "generate_scene_plan", fake_generate_scene_plan)

    ns = Namespace(
        idea="Luxury energy drink vlog",
        scenes=2,
        character_description="Nyx Cipher — neon rooftop influencer",
        character_traits="playful, confident",
        context="Keep it upbeat",
        reference=None,
        video_type="vlog",
        video_characteristics="bright, high-definition, comedic",
        camera_angle="front",
        model=None,
        save=None,
        json=True,
    )

    cli.cmd_plan(ns)

    out = capsys.readouterr().out
    assert "clip-1" in out
    assert called["number_of_scenes"] == 2
    assert called["character_description"].startswith("Nyx Cipher")
    assert called["video_type"] == "vlog"


def test_cmd_plan_loads_reference(monkeypatch, capsys, tmp_path):
    called = {}

    def fake_generate_scene_plan(*args, **kwargs):
        called.update(kwargs)
        return _make_plan()

    monkeypatch.setattr(cli.veo, "init", lambda: None)
    monkeypatch.setattr(cli.veo, "generate_scene_plan", fake_generate_scene_plan)

    ref_path = tmp_path / "ref.json"
    ref_payload = [{
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
    }]
    ref_path.write_text(json.dumps(ref_payload), encoding="utf-8")

    ns = Namespace(
        idea="Luxury energy drink vlog",
        scenes=1,
        character_description=None,
        character_traits=None,
        context=None,
        reference=[str(ref_path)],
        video_type="video",
        video_characteristics="realistic, 4k, cinematic",
        camera_angle="front",
        model="gemini-pro",
        save=tmp_path / "plan.json",
        json=False,
    )

    cli.cmd_plan(ns)

    out = capsys.readouterr().out
    assert "Generated plan" in out
    assert called["character_references"] and called["character_references"][0]["name"] == "Nyx Cipher"
    assert called["model"] == "gemini-pro"
    assert called["save_path"] == ns.save


def test_cmd_plan_missing_reference(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.veo, "init", lambda: None)
    monkeypatch.setattr(cli.veo, "generate_scene_plan", lambda *a, **k: _make_plan())

    ns = Namespace(
        idea="Idea",
        scenes=1,
        character_description=None,
        character_traits=None,
        context=None,
        reference=[str(tmp_path / "missing.json")],
        video_type="video",
        video_characteristics="realistic",
        camera_angle="front",
        model=None,
        save=None,
        json=True,
    )

    with pytest.raises(FileNotFoundError):
        cli.cmd_plan(ns)


def test_cmd_plan_execute_runs_executor(monkeypatch, capsys):
    called = {}

    def fake_execute_scene_plan(plan, **kwargs):
        called["plan"] = plan
        called.update(kwargs)

        clip_result = SimpleNamespace(path=Path("/tmp/clip.mp4"), to_dict=lambda: {"path": "/tmp/clip.mp4"})
        return SimpleNamespace(
            clip_results=[clip_result],
            final_result=SimpleNamespace(path=Path("/tmp/final.mp4"), to_dict=lambda: {"path": "/tmp/final.mp4"}),
            to_dict=lambda: {
                "clips": [{"prompt": "", "result": {"path": "/tmp/clip.mp4"}}],
                "final_result": {"path": "/tmp/final.mp4"},
            },
        )

    monkeypatch.setattr(cli.veo, "init", lambda: None)
    monkeypatch.setattr(cli.veo, "execute_scene_plan", fake_execute_scene_plan)

    ns = Namespace(
        plan="output-plans/x402_plan.json",
        model=None,
        overlap=0.75,
        no_stitch=False,
        seed_last_frame=True,
        seed_offset=-0.25,
        json=False,
    )

    cli.cmd_plan_execute(ns)
    out = capsys.readouterr().out
    assert "Rendered 1 clip(s)" in out
    assert called["plan"] == "output-plans/x402_plan.json"
    assert called["model"] == "veo-3.0-generate-001"
    assert called["overlap"] == 0.75
    assert called["auto_seed_last_frame"] is True
    assert called["seed_frame_offset"] == -0.25
    assert called["stitch"] is True


def test_cmd_plan_execute_json(monkeypatch, capsys):
    monkeypatch.setattr(cli.veo, "init", lambda: None)

    result_obj = SimpleNamespace(
        clip_results=[SimpleNamespace(path=Path("/tmp/clip.mp4"), to_dict=lambda: {"path": "clip"})],
        final_result=None,
        to_dict=lambda: {"clips": [{"prompt": "", "result": {"path": "clip"}}], "final_result": None},
    )

    monkeypatch.setattr(cli.veo, "execute_scene_plan", lambda *a, **k: result_obj)

    ns = Namespace(
        plan="plan.json",
        model="veo-3.0-generate-001",
        overlap=1.0,
        no_stitch=True,
        seed_last_frame=False,
        seed_offset=-0.5,
        json=True,
    )

    cli.cmd_plan_execute(ns)
    out = capsys.readouterr().out
    assert "\"clips\"" in out


def test_cmd_plan_run(monkeypatch, capsys, tmp_path):
    plan_called = {}
    exec_called = {}

    class StubPlan(SimpleNamespace):
        def model_dump_json(self):
            return json.dumps({"clips": [{"id": "clip_001"}]})

    plan_obj = StubPlan(clips=[SimpleNamespace(id="clip_001")])

    def fake_generate_scene_plan(*args, **kwargs):
        plan_called["args"] = args
        plan_called["kwargs"] = kwargs
        return plan_obj

    def fake_execute_scene_plan(plan, **kwargs):
        exec_called["plan"] = plan
        exec_called["kwargs"] = kwargs
        clip_result = SimpleNamespace(path=Path("/tmp/clip.mp4"), to_dict=lambda: {"path": "/tmp/clip.mp4"})
        return SimpleNamespace(
            clip_results=[clip_result],
            final_result=SimpleNamespace(path=Path("/tmp/final.mp4"), to_dict=lambda: {"path": "/tmp/final.mp4"}),
            to_dict=lambda: {
                "clips": [{"prompt": "", "result": {"path": "/tmp/clip.mp4"}}],
                "final_result": {"path": "/tmp/final.mp4"},
            },
        )

    monkeypatch.setattr(cli.veo, "init", lambda: None)
    monkeypatch.setattr(cli.veo, "generate_scene_plan", fake_generate_scene_plan)
    monkeypatch.setattr(cli.veo, "execute_scene_plan", fake_execute_scene_plan)

    plan_path = tmp_path / "plan.json"

    ns = Namespace(
        idea="Idea",
        scenes=3,
        character_description=None,
        character_traits=None,
        context=None,
        reference=None,
        video_type=None,
        video_characteristics=None,
        camera_angle=None,
        plan_model="gemini-2.5-pro",
        save_plan=str(plan_path),
        execute_model="veo-3.0-generate-001",
        overlap=0.5,
        no_stitch=False,
        seed_last_frame=True,
        seed_offset=-0.25,
        json=False,
    )

    cli.cmd_plan_run(ns)
    out = capsys.readouterr().out
    assert "Generated plan" in out
    assert "Rendered 1 clip" in out
    assert "Final video" in out
    assert "Plan saved" in out

    assert plan_called["args"] == ("Idea",)
    assert plan_called["kwargs"]["number_of_scenes"] == 3
    assert plan_called["kwargs"]["model"] == "gemini-2.5-pro"
    assert plan_called["kwargs"]["save_path"] == str(plan_path)

    assert exec_called["plan"] is plan_obj
    assert exec_called["kwargs"]["model"] == "veo-3.0-generate-001"
    assert exec_called["kwargs"]["overlap"] == 0.5
    assert exec_called["kwargs"]["auto_seed_last_frame"] is True
    assert exec_called["kwargs"]["seed_frame_offset"] == -0.25


def test_cmd_plan_run_json(monkeypatch, capsys):
    plan_obj = SimpleNamespace(
        clips=[SimpleNamespace(id="clip_001")],
        model_dump_json=lambda: json.dumps({"clips": [{"id": "clip_001"}]})
    )

    monkeypatch.setattr(cli.veo, "init", lambda: None)
    monkeypatch.setattr(cli.veo, "generate_scene_plan", lambda *a, **k: plan_obj)

    exec_result = SimpleNamespace(
        clip_results=[SimpleNamespace(path=Path("/tmp/clip.mp4"), to_dict=lambda: {"path": "clip"})],
        final_result=None,
        to_dict=lambda: {"clips": [{"prompt": "", "result": {"path": "clip"}}], "final_result": None},
    )

    def fake_execute(plan, **kwargs):
        return exec_result

    monkeypatch.setattr(cli.veo, "execute_scene_plan", fake_execute)

    ns = Namespace(
        idea="Idea",
        scenes=1,
        character_description=None,
        character_traits=None,
        context=None,
        reference=None,
        video_type=None,
        video_characteristics=None,
        camera_angle=None,
        plan_model=None,
        save_plan=None,
        execute_model=None,
        overlap=1.0,
        no_stitch=False,
        seed_last_frame=False,
        seed_offset=-0.5,
        json=True,
    )

    cli.cmd_plan_run(ns)
    out = capsys.readouterr().out
    assert "\"plan\"" in out and "\"execution\"" in out
