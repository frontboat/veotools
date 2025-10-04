"""Tests for default parameter handling in video generation."""

from __future__ import annotations

import pytest

from veotools.generate.video import _apply_default_person_generation


@pytest.mark.parametrize(
    "model, mode, expected",
    [
        ("veo-3.0-generate-001", "text", "allow_all"),
        ("models/veo-3.0-generate-001", "text", "allow_all"),
        ("veo-3.0-generate-001", "image", "allow_adult"),
        ("models/veo-3.0-fast-generate-001", "image", "allow_adult"),
        ("veo-3.0-generate-001", "video", "allow_adult"),
    ],
)
def test_apply_default_person_generation(model, mode, expected):
    params = {}
    _apply_default_person_generation(model, mode, params)
    assert params["person_generation"] == expected


def test_apply_default_person_generation_preserves_existing():
    params = {"person_generation": "allow_all"}
    _apply_default_person_generation("veo-3.0-generate-001", "image", params)
    assert params["person_generation"] == "allow_all"
