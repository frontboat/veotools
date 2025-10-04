"""Tests for veotools.core module."""

import os
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from veotools.core import VeoClient, StorageManager, ProgressTracker, ModelConfig


class TestVeoClient:
    """Test cases for VeoClient."""
    
    @pytest.mark.unit
    def test_singleton_pattern(self):
        """Test that VeoClient follows singleton pattern."""
        client1 = VeoClient()
        client2 = VeoClient()
        assert client1 is client2
    
    @pytest.mark.unit
    def test_initialization_with_api_key(self, monkeypatch):
        """Test VeoClient initializes with API key from environment."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
        
        # Clear the singleton instance
        VeoClient._instance = None
        VeoClient._client = None
        VeoClient._provider = None
        
        client = VeoClient()
        assert client._client is not None
    
    @pytest.mark.unit
    def test_initialization_without_api_key_raises_error(self, monkeypatch):
        """Test VeoClient raises error when API key is missing."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("DAYDREAMS_API_KEY", raising=False)
        monkeypatch.delenv("VEO_PROVIDER", raising=False)

        # Clear the singleton instance
        VeoClient._instance = None
        VeoClient._client = None
        VeoClient._provider = None
        
        with pytest.raises(ValueError, match="GEMINI_API_KEY not found"):
            VeoClient()
    
    @pytest.mark.unit
    @patch('veotools.core.genai.Client')
    def test_client_property(self, mock_genai_client):
        """Test client property returns the genai client."""
        mock_genai_client.return_value = Mock()
        
        # Clear the singleton instance
        VeoClient._instance = None
        VeoClient._client = None
        VeoClient._provider = None
        
        client = VeoClient()
        assert client.client == client._client

    @pytest.mark.unit
    @patch('veotools.core.DaydreamsRouterClient')
    def test_daydreams_provider_initialization(self, mock_router, monkeypatch):
        """Ensure VeoClient initializes the Daydreams Router client when configured."""
        monkeypatch.setenv("VEO_PROVIDER", "daydreams")
        monkeypatch.setenv("DAYDREAMS_API_KEY", "router-key")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        mock_router.return_value = Mock()

        VeoClient._instance = None
        VeoClient._client = None
        VeoClient._provider = None

        client = VeoClient()

        mock_router.assert_called_once_with(api_key="router-key", base_url=None)
        assert client.provider == "daydreams"


class TestStorageManager:
    """Test cases for StorageManager."""
    
    @pytest.mark.unit
    def test_initialization_with_base_path(self, tmp_path):
        """Test StorageManager initializes with provided base path."""
        base_path = tmp_path / "custom_output"
        manager = StorageManager(base_path=str(base_path))
        
        assert manager.base_path == base_path
        assert manager.videos_dir == base_path / "videos"
        assert manager.frames_dir == base_path / "frames"
        assert manager.temp_dir == base_path / "temp"
        
        # Check directories were created
        assert manager.videos_dir.exists()
        assert manager.frames_dir.exists()
        assert manager.temp_dir.exists()
    
    @pytest.mark.unit
    def test_initialization_with_env_variable(self, tmp_path, monkeypatch):
        """Test StorageManager uses VEO_OUTPUT_DIR environment variable."""
        env_path = tmp_path / "env_output"
        monkeypatch.setenv("VEO_OUTPUT_DIR", str(env_path))
        
        manager = StorageManager()
        assert manager.base_path == env_path
    
    @pytest.mark.unit
    def test_get_video_path(self, temp_output_dir):
        """Test get_video_path returns correct path."""
        manager = StorageManager(base_path=str(temp_output_dir))
        video_path = manager.get_video_path("test_video.mp4")
        
        assert video_path == temp_output_dir / "videos" / "test_video.mp4"
    
    @pytest.mark.unit
    def test_get_frame_path(self, temp_output_dir):
        """Test get_frame_path returns correct path."""
        manager = StorageManager(base_path=str(temp_output_dir))
        frame_path = manager.get_frame_path("frame_001.jpg")
        
        assert frame_path == temp_output_dir / "frames" / "frame_001.jpg"
    
    @pytest.mark.unit
    def test_get_temp_path(self, temp_output_dir):
        """Test get_temp_path returns correct path."""
        manager = StorageManager(base_path=str(temp_output_dir))
        temp_path = manager.get_temp_path("temp_file.tmp")
        
        assert temp_path == temp_output_dir / "temp" / "temp_file.tmp"
    
    @pytest.mark.unit
    def test_cleanup_temp(self, temp_output_dir):
        """Test cleanup_temp removes all files from temp directory."""
        manager = StorageManager(base_path=str(temp_output_dir))
        
        # Create some temp files
        temp_file1 = manager.temp_dir / "file1.tmp"
        temp_file2 = manager.temp_dir / "file2.tmp"
        temp_file1.write_text("temp content 1")
        temp_file2.write_text("temp content 2")
        
        assert temp_file1.exists()
        assert temp_file2.exists()
        
        # Clean up
        manager.cleanup_temp()
        
        assert not temp_file1.exists()
        assert not temp_file2.exists()
        assert manager.temp_dir.exists()  # Directory should still exist
    
    @pytest.mark.unit
    def test_get_url_with_existing_file(self, temp_output_dir):
        """Test get_url returns file URL for existing file."""
        manager = StorageManager(base_path=str(temp_output_dir))
        
        # Create a test file
        test_file = manager.videos_dir / "test.mp4"
        test_file.write_text("test content")
        
        url = manager.get_url(test_file)
        assert url == f"file://{test_file.absolute()}"
    
    @pytest.mark.unit
    def test_get_url_with_nonexistent_file(self, temp_output_dir):
        """Test get_url returns None for non-existent file."""
        manager = StorageManager(base_path=str(temp_output_dir))
        
        test_file = manager.videos_dir / "nonexistent.mp4"
        url = manager.get_url(test_file)
        assert url is None


class TestProgressTracker:
    """Test cases for ProgressTracker."""
    
    @pytest.mark.unit
    def test_initialization_with_callback(self):
        """Test ProgressTracker initializes with custom callback."""
        custom_callback = Mock()
        tracker = ProgressTracker(callback=custom_callback)
        
        assert tracker.callback == custom_callback
        assert tracker.current_progress == 0
    
    @pytest.mark.unit
    def test_initialization_without_callback(self):
        """Test ProgressTracker uses default callback when none provided."""
        tracker = ProgressTracker()
        
        assert tracker.callback == tracker.default_progress
        assert tracker.current_progress == 0
    
    @pytest.mark.unit
    def test_update_progress(self):
        """Test update method updates progress and calls callback."""
        callback = Mock()
        tracker = ProgressTracker(callback=callback)
        
        tracker.update("Processing", 50)
        
        assert tracker.current_progress == 50
        callback.assert_called_once_with("Processing", 50)
    
    @pytest.mark.unit
    @pytest.mark.parametrize("progress,expected", [
        (0, 0),
        (50, 50),
        (100, 100),
        (150, 150),  # No capping in actual implementation
        (-10, -10),  # No flooring in actual implementation
    ])
    def test_progress_values(self, progress, expected):
        """Test progress values are stored correctly."""
        tracker = ProgressTracker()
        tracker.update("Test", progress)
        
        assert tracker.current_progress == expected
    
    @pytest.mark.unit
    def test_start_and_complete_methods(self):
        """Test start and complete helper methods."""
        callback = Mock()
        tracker = ProgressTracker(callback=callback)
        
        tracker.start("Beginning")
        assert tracker.current_progress == 0
        callback.assert_called_with("Beginning", 0)
        
        tracker.complete("Finished")
        assert tracker.current_progress == 100
        callback.assert_called_with("Finished", 100)


class TestModelConfig:
    """Test cases for ModelConfig."""
    
    @pytest.mark.unit
    def test_get_config(self):
        """Test get_config returns correct model configuration."""
        config = ModelConfig.get_config("veo-3.0-fast-generate-preview")
        
        assert config["name"] == "Veo 3.0 Fast"
        assert config["supports_duration"] is False
        assert config["supports_aspect_ratio"] is True
        assert config["default_duration"] == 8
        
    @pytest.mark.unit
    def test_get_config_with_models_prefix(self):
        """Test get_config handles models/ prefix."""
        config = ModelConfig.get_config("models/veo-3.0-fast-generate-preview")
        
        assert config["name"] == "Veo 3.0 Fast"
        assert config["supports_duration"] is False
    
    @pytest.mark.unit
    def test_get_config_unknown_model(self):
        """Test get_config returns default for unknown model."""
        config = ModelConfig.get_config("unknown-model")
        
        # Should return default (veo-3.0-fast-generate-preview)
        assert config["name"] == "Veo 3.0 Fast"
        assert config["default_duration"] == 8
    
    @pytest.mark.unit
    @patch('veotools.core.types.GenerateVideosConfig')
    def test_build_generation_config(self, mock_config_class):
        """Test build_generation_config creates proper config."""
        mock_config_instance = Mock()
        mock_config_class.return_value = mock_config_instance
        
        result = ModelConfig.build_generation_config(
            "veo-3.0-fast-generate-preview",
            number_of_videos=2,
            aspect_ratio="16:9"
        )
        
        # Should return the mock instance
        assert result == mock_config_instance
        
        # Should call the config constructor
        mock_config_class.assert_called_once()
        call_args = mock_config_class.call_args[1]
        assert call_args["number_of_videos"] == 2
        assert "aspect_ratio" in call_args
    
    @pytest.mark.unit
    def test_model_configurations(self):
        """Test that all models have required configuration keys."""
        required_keys = ["name", "supports_duration", "supports_enhance", 
                        "supports_fps", "supports_aspect_ratio", "supports_audio",
                        "default_duration", "generation_time"]
        
        for model_id in ModelConfig.MODELS:
            config = ModelConfig.MODELS[model_id]
            for key in required_keys:
                assert key in config, f"Model {model_id} missing key: {key}"

    @pytest.mark.unit
    def test_normalize_model_aliases(self):
        """Alias mappings normalize to canonical model ids."""
        assert ModelConfig.normalize_model("google/veo-3") == "veo-3.0-generate-preview"
        assert ModelConfig.normalize_model("models/veo-3.0-fast-generate-preview") == "veo-3.0-fast-generate-preview"
        assert ModelConfig.normalize_model(None) == "veo-3.0-fast-generate-preview"

    @pytest.mark.unit
    def test_daydreams_model_mapping(self):
        """Canonical models map to Daydreams Router identifiers."""
        assert ModelConfig.to_daydreams_model("veo-3.0-fast-generate-preview") == "google/veo-3-fast"
        assert ModelConfig.to_daydreams_model("veo-3.0-generate-001") == "google/veo-3"
        assert ModelConfig.to_daydreams_model("google/veo-3") == "google/veo-3"
        assert ModelConfig.to_daydreams_model("unknown-model") is None
        assert ModelConfig.to_daydreams_slug("veo-3.0-fast-generate-001") == "veo-3-fast"
        assert ModelConfig.to_daydreams_slug("google/veo-3") == "veo-3"


# Integration tests (marked for conditional execution)
class TestIntegration:
    """Integration tests that may interact with external services."""
    
    @pytest.mark.integration
    @pytest.mark.requires_ffmpeg
    def test_storage_manager_with_real_filesystem(self, tmp_path):
        """Test StorageManager with real filesystem operations."""
        manager = StorageManager(base_path=str(tmp_path))
        
        # Create a real file
        video_path = manager.get_video_path("test.mp4")
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"video content")
        
        # Test URL generation
        url = manager.get_url(video_path)
        assert url is not None
        assert "file://" in url
        assert str(video_path.absolute()) in url
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_progress_tracker_with_logging(self, caplog):
        """Test ProgressTracker default logging behavior."""
        caplog.set_level(logging.INFO)
        
        tracker = ProgressTracker()
        
        # Simulate progress updates
        tracker.update("Processing", 50)
        tracker.complete("Done")
        
        # Check log messages
        assert "Processing: 50%" in caplog.text
        assert "Done: 100%" in caplog.text
