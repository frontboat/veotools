"""Tests for Veo 3.1 model configuration."""

import pytest

from veotools.core import ModelConfig


def test_model_config_v31_capabilities():
    config = ModelConfig.get_config("veo-3.1-generate-preview")

    assert config["supports_reference_images"] is True
    assert config["supports_video_extension"] is True
    assert config["supports_last_frame"] is True
    assert config["supports_resolution"] is True
    assert config["allowed_durations"] == [4, 6, 8]


def test_build_generation_config_v31_rejects_invalid_duration():
    with pytest.raises(ValueError, match="duration_seconds"):
        ModelConfig.build_generation_config(
            "veo-3.1-generate-preview",
            duration_seconds=5,
        )


def test_build_generation_config_v31_rejects_invalid_resolution():
    with pytest.raises(ValueError, match="resolution"):
        ModelConfig.build_generation_config(
            "veo-3.1-generate-preview",
            resolution="4k",
        )


def test_build_generation_config_v31_rejects_invalid_seed():
    with pytest.raises(ValueError, match="seed"):
        ModelConfig.build_generation_config(
            "veo-3.1-generate-preview",
            seed=-1,
        )
