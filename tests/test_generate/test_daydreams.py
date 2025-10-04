"""Daydreams Router specific generation tests."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from veotools.models import JobStatus
from veotools.generate.video import generate_from_text


@patch("veotools.generate.video.VeoClient")
def test_generate_from_text_daydreams_success(mock_client_cls, tmp_path, monkeypatch):
    """Text-to-video generation succeeds via the Daydreams Router provider."""
    monkeypatch.setenv("VEO_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr("veotools.generate.video.time.sleep", lambda _: None)
    monkeypatch.setattr(
        "veotools.generate.video.get_video_info",
        lambda _: {"fps": 24, "duration": 8, "width": 1280, "height": 720},
    )

    router = Mock()
    router.submit_video_job.return_value = {"job_id": "job-123", "status": "queued"}
    router.get_video_job.side_effect = [
        {"status": "processing"},
        {
            "status": "succeeded",
            "assets": [
                {
                    "url": "https://example.com/video.mp4",
                    "mime_type": "video/mp4",
                }
            ],
        },
    ]
    router.download_asset.side_effect = lambda _url, output_path: Path(output_path).write_bytes(b"video-data")

    mock_client_cls.return_value = SimpleNamespace(provider="daydreams", client=router)

    result = generate_from_text("A calm ocean at sunset", model="google/veo-3")

    assert result.status == JobStatus.COMPLETE
    assert result.path and result.path.exists()
    router.submit_video_job.assert_called_once()
    args, kwargs = router.submit_video_job.call_args
    assert args[0] == "google/veo-3"
    assert kwargs.get("slug") == "veo-3"
    assert router.get_video_job.call_count == 2
    router.download_asset.assert_called_once()
