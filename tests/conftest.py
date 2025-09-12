"""Shared fixtures and configuration for veotools tests."""

import os
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock
import pytest


@pytest.fixture(autouse=True)
def mock_api_key(monkeypatch):
    """Automatically set a test API key for all tests."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-12345")


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory for tests."""
    output_dir = tmp_path / "test_output"
    output_dir.mkdir()
    (output_dir / "videos").mkdir()
    (output_dir / "frames").mkdir()
    (output_dir / "temp").mkdir()
    return output_dir


@pytest.fixture
def mock_veo_client(monkeypatch):
    """Mock the VeoClient to avoid real API calls."""
    mock_client = Mock()
    mock_client.client = Mock()
    monkeypatch.setattr("veotools.core.VeoClient", lambda: mock_client)
    return mock_client


@pytest.fixture
def sample_video_config():
    """Provide a sample video configuration for tests."""
    return {
        "prompt": "A serene mountain landscape",
        "model": "veo-3.0-fast-generate-preview",
        "duration": 10,
        "resolution": "1080p",
        "aspect_ratio": "16:9"
    }


@pytest.fixture
def mock_video_file(tmp_path):
    """Create a mock video file for testing."""
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"fake video content for testing")
    return str(video_file)


@pytest.fixture
def mock_image_file(tmp_path):
    """Create a mock image file for testing."""
    image_file = tmp_path / "test_image.jpg"
    image_file.write_bytes(b"fake image content for testing")
    return str(image_file)


@pytest.fixture
def mock_ffmpeg_output():
    """Mock ffmpeg output for video info extraction."""
    return {
        "streams": [{
            "codec_type": "video",
            "width": 1920,
            "height": 1080,
            "duration": "10.5",
            "r_frame_rate": "30/1"
        }],
        "format": {
            "duration": "10.5",
            "size": "5242880",
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2"
        }
    }


@pytest.fixture
def mock_genai_response():
    """Mock Google GenAI API response."""
    mock_response = Mock()
    mock_response.name = "operations/video-generation-12345"
    mock_response.done = False
    mock_response.metadata = {"progress_percent": 0}
    return mock_response


@pytest.fixture
def mock_completed_video_response():
    """Mock completed video generation response."""
    mock_response = Mock()
    mock_response.done = True
    mock_response.result = Mock()
    mock_response.result.video = Mock()
    mock_response.result.video.uri = "https://example.com/generated_video.mp4"
    return mock_response


@pytest.fixture
def mock_job_store(tmp_path):
    """Create a mock job store for testing."""
    jobs_dir = tmp_path / "ops"
    jobs_dir.mkdir()
    
    class MockJobStore:
        def __init__(self):
            self.jobs_dir = jobs_dir
        
        def save_job(self, job_id, data):
            job_file = self.jobs_dir / f"{job_id}.json"
            job_file.write_text(json.dumps(data))
        
        def load_job(self, job_id):
            job_file = self.jobs_dir / f"{job_id}.json"
            if job_file.exists():
                return json.loads(job_file.read_text())
            return None
        
        def delete_job(self, job_id):
            job_file = self.jobs_dir / f"{job_id}.json"
            if job_file.exists():
                job_file.unlink()
    
    return MockJobStore()


@pytest.fixture(scope="session")
def test_media_files(tmp_path_factory):
    """Create test media files that persist for the session."""
    media_dir = tmp_path_factory.mktemp("test_media")
    
    # Create multiple test files
    files = {
        "video1.mp4": b"fake video 1 content",
        "video2.mp4": b"fake video 2 content", 
        "image1.jpg": b"fake image 1 content",
        "image2.png": b"fake image 2 content",
    }
    
    created_files = {}
    for filename, content in files.items():
        filepath = media_dir / filename
        filepath.write_bytes(content)
        created_files[filename.split('.')[0]] = str(filepath)
    
    return created_files


@pytest.fixture
def mock_progress_callback():
    """Create a mock progress callback for testing."""
    callback = Mock()
    callback.side_effect = lambda msg, pct: print(f"Progress: {msg} - {pct}%")
    return callback


# Markers for conditional test execution
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "requires_ffmpeg: mark test as requiring ffmpeg installation"
    )
    config.addinivalue_line(
        "markers", "requires_api_key: mark test as requiring valid API key"
    )


# Skip tests that require ffmpeg if not installed
@pytest.fixture(autouse=True)
def skip_if_no_ffmpeg(request):
    """Skip tests marked with requires_ffmpeg if ffmpeg is not installed."""
    if request.node.get_closest_marker("requires_ffmpeg"):
        try:
            import subprocess
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("ffmpeg not installed")