"""Tests for person_generation validation rules."""

import pytest

from veotools.generate.video import _validate_person_generation


@pytest.mark.parametrize(
    "model, mode, value",
    [
        ("veo-3.1-generate-preview", "text", "allow_all"),
        ("veo-3.1-generate-preview", "image", "allow_adult"),
        ("veo-3.0-generate-preview", "text", "allow_all"),
        ("veo-3.0-generate-preview", "video", "allow_adult"),
        ("veo-2.0-generate-001", "text", "dont_allow"),
        ("veo-2.0-generate-001", "image", "allow_adult"),
    ],
)
def test_validate_person_generation_allows(model, mode, value):
    _validate_person_generation(model, mode, value)


@pytest.mark.parametrize(
    "model, mode, value",
    [
        ("veo-3.1-generate-preview", "text", "allow_adult"),
        ("veo-3.1-generate-preview", "image", "allow_all"),
        ("veo-3.0-generate-preview", "text", "allow_adult"),
        ("veo-3.0-generate-preview", "image", "allow_all"),
        ("veo-2.0-generate-001", "image", "allow_all"),
    ],
)
def test_validate_person_generation_rejects(model, mode, value):
    with pytest.raises(ValueError, match="person_generation"):
        _validate_person_generation(model, mode, value)
