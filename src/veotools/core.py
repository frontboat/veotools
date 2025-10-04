import os
import logging
from pathlib import Path
from typing import Optional, Callable
from dotenv import load_dotenv
from google import genai
from google.genai import types

from .providers import DaydreamsRouterClient

load_dotenv()

class VeoClient:
    """Singleton client for Google GenAI API interactions.
    
    This class implements a singleton pattern to ensure only one client instance
    is created throughout the application lifecycle. It manages the authentication
    and connection to Google's Generative AI API.
    
    Attributes:
        client: The underlying Google GenAI client instance.
    
    Raises:
        ValueError: If GEMINI_API_KEY environment variable is not set.
    
    Examples:
        >>> client = VeoClient()
        >>> api_client = client.client
        >>> # Use api_client for API calls
    """
    _instance = None
    _client = None
    _provider = None
    
    def __new__(cls):
        """Create or return the singleton instance.
        
        Returns:
            VeoClient: The singleton VeoClient instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the GenAI client with API key from environment.
        
        The client is only initialized once, even if __init__ is called multiple times.
        
        Raises:
            ValueError: If GEMINI_API_KEY is not found in environment variables.
        """
        cls = type(self)
        if cls._client is None:
            provider = (os.getenv("VEO_PROVIDER", "google") or "google").strip().lower()
            cls._provider = provider

            if provider == "daydreams":
                api_key = os.getenv("DAYDREAMS_API_KEY")
                if not api_key:
                    raise ValueError("DAYDREAMS_API_KEY not found in environment")
                base_url = os.getenv("DAYDREAMS_BASE_URL")
                cls._client = DaydreamsRouterClient(api_key=api_key, base_url=base_url)
            else:
                api_key = os.getenv('GEMINI_API_KEY')
                if not api_key:
                    raise ValueError("GEMINI_API_KEY not found in .env file")
                cls._provider = "google"
                cls._client = genai.Client(api_key=api_key)
    
    @property
    def client(self):
        """Get the Google GenAI client instance.
        
        Returns:
            genai.Client: The initialized GenAI client.
        """
        return type(self)._client

    @property
    def provider(self) -> str:
        """Return the active provider identifier (google or daydreams)."""

        provider = type(self)._provider
        return provider if provider else "google"

class StorageManager:
    def __init__(self, base_path: Optional[str] = None):
        """Manage output directories for videos, frames, and temp files.

        Default resolution order for base path:
        1. VEO_OUTPUT_DIR environment variable (if set)
        2. Current working directory (./output)
        3. Package-adjacent directory (../output) as a last resort
        """
        resolved_base: Path

        # 1) Environment override
        env_base = os.getenv("VEO_OUTPUT_DIR")
        if base_path:
            resolved_base = Path(base_path)
        elif env_base:
            resolved_base = Path(env_base)
        else:
            # 2) Prefer CWD/output for installed packages (CLI/scripts)
            cwd_candidate = Path.cwd() / "output"
            try:
                cwd_candidate.mkdir(parents=True, exist_ok=True)
                resolved_base = cwd_candidate
            except Exception:
                # 3) As a last resort, place beside the installed package
                try:
                    package_root = Path(__file__).resolve().parents[2]
                    candidate = package_root / "output"
                    candidate.mkdir(parents=True, exist_ok=True)
                    resolved_base = candidate
                except Exception:
                    # Final fallback: user home
                    resolved_base = Path.home() / "output"

        self.base_path = resolved_base
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.videos_dir = self.base_path / "videos"
        self.frames_dir = self.base_path / "frames"
        self.temp_dir = self.base_path / "temp"

        for dir_path in [self.videos_dir, self.frames_dir, self.temp_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def get_video_path(self, filename: str) -> Path:
        """Get the full path for a video file.
        
        Args:
            filename: Name of the video file.
            
        Returns:
            Path: Full path to the video file in the videos directory.
            
        Examples:
            >>> manager = StorageManager()
            >>> path = manager.get_video_path("output.mp4")
            >>> print(path)  # /path/to/output/videos/output.mp4
        """
        return self.videos_dir / filename
    
    def get_frame_path(self, filename: str) -> Path:
        """Get the full path for a frame image file.
        
        Args:
            filename: Name of the frame file.
            
        Returns:
            Path: Full path to the frame file in the frames directory.
            
        Examples:
            >>> manager = StorageManager()
            >>> path = manager.get_frame_path("frame_001.jpg")
            >>> print(path)  # /path/to/output/frames/frame_001.jpg
        """
        return self.frames_dir / filename
    
    def get_temp_path(self, filename: str) -> Path:
        """Get the full path for a temporary file.
        
        Args:
            filename: Name of the temporary file.
            
        Returns:
            Path: Full path to the file in the temp directory.
            
        Examples:
            >>> manager = StorageManager()
            >>> path = manager.get_temp_path("processing.tmp")
            >>> print(path)  # /path/to/output/temp/processing.tmp
        """
        return self.temp_dir / filename
    
    def cleanup_temp(self):
        """Remove all files from the temporary directory.
        
        This method safely removes all files in the temp directory while preserving
        the directory structure. Errors during deletion are silently ignored.
        
        Examples:
            >>> manager = StorageManager()
            >>> manager.cleanup_temp()
            >>> # All temp files are now deleted
        """
        for file in self.temp_dir.glob("*"):
            try:
                file.unlink()
            except:
                pass
    
    def get_url(self, path: Path) -> Optional[str]:
        """Convert a file path to a file:// URL.
        
        Args:
            path: Path to the file.
            
        Returns:
            Optional[str]: File URL if the file exists, None otherwise.
            
        Examples:
            >>> manager = StorageManager()
            >>> video_path = manager.get_video_path("test.mp4")
            >>> url = manager.get_url(video_path)
            >>> print(url)  # file:///absolute/path/to/output/videos/test.mp4
        """
        if path.exists():
            return f"file://{path.absolute()}"
        return None

class ProgressTracker:
    """Track and report progress for long-running operations.
    
    This class provides a simple interface for tracking progress updates during
    video generation and processing operations. It supports custom callbacks
    or falls back to logging.
    
    Attributes:
        callback: Function to call with progress updates.
        current_progress: Current progress percentage (0-100).
        logger: Logger instance for default progress reporting.
    
    Examples:
        >>> def my_callback(msg: str, pct: int):
        ...     print(f"{msg}: {pct}%")
        >>> tracker = ProgressTracker(callback=my_callback)
        >>> tracker.start("Processing")
        >>> tracker.update("Halfway", 50)
        >>> tracker.complete("Done")
    """
    def __init__(self, callback: Optional[Callable] = None):
        """Initialize the progress tracker.
        
        Args:
            callback: Optional callback function that receives (message, percent).
                     If not provided, uses default logging.
        """
        self.callback = callback or self.default_progress
        self.current_progress = 0
        self.logger = logging.getLogger(__name__)
    
    def default_progress(self, message: str, percent: int):
        """Default progress callback that logs to the logger.
        
        Args:
            message: Progress message.
            percent: Progress percentage.
        """
        self.logger.info(f"{message}: {percent}%")
    
    def update(self, message: str, percent: int):
        """Update progress and trigger callback.
        
        Args:
            message: Progress message to display.
            percent: Current progress percentage (0-100).
        """
        self.current_progress = percent
        self.callback(message, percent)
    
    def start(self, message: str = "Starting"):
        """Mark the start of an operation (0% progress).
        
        Args:
            message: Starting message, defaults to "Starting".
        """
        self.update(message, 0)
    
    def complete(self, message: str = "Complete"):
        """Mark the completion of an operation (100% progress).
        
        Args:
            message: Completion message, defaults to "Complete".
        """
        self.update(message, 100)

class ModelConfig:
    """Configuration and capabilities for different Veo video generation models."""

    DEFAULT_MODEL = "veo-3.0-fast-generate-preview"

    ALIASES = {
        "veo-3": "veo-3.0-generate-preview",
        "veo-3.0": "veo-3.0-generate-preview",
        "google/veo-3": "veo-3.0-generate-preview",
        "models/veo-3.0-generate-preview": "veo-3.0-generate-preview",
        "veo-3-fast": "veo-3.0-fast-generate-preview",
        "veo-3.0-fast": "veo-3.0-fast-generate-preview",
        "google/veo-3-fast": "veo-3.0-fast-generate-preview",
        "models/veo-3.0-fast-generate-preview": "veo-3.0-fast-generate-preview",
        "veo-3.0-generate-001": "veo-3.0-generate-001",
        "veo-3.0-fast-generate-001": "veo-3.0-fast-generate-001",
    }

    DAYDREAMS_MODEL_IDS = {
        "veo-3.0-generate-preview": "google/veo-3",
        "veo-3.0-fast-generate-preview": "google/veo-3-fast",
        "veo-3.0-generate-001": "google/veo-3",
        "veo-3.0-fast-generate-001": "google/veo-3-fast",
    }

    DAYDREAMS_SLUGS = {
        "veo-3.0-generate-preview": "veo-3",
        "veo-3.0-generate-001": "veo-3",
        "veo-3.0-fast-generate-preview": "veo-3-fast",
        "veo-3.0-fast-generate-001": "veo-3-fast",
    }

    MODELS = {
        "veo-3.0-fast-generate-preview": {
            "name": "Veo 3.0 Fast",
            "supports_duration": False,
            "supports_enhance": False,
            "supports_fps": False,
            "supports_aspect_ratio": True,
            "supports_audio": True,
            "default_duration": 8,
            "generation_time": 60,
        },
        "veo-3.0-generate-preview": {
            "name": "Veo 3.0",
            "supports_duration": False,
            "supports_enhance": False,
            "supports_fps": False,
            "supports_aspect_ratio": True,
            "supports_audio": True,
            "default_duration": 8,
            "generation_time": 120,
        },
        "veo-2.0-generate-001": {
            "name": "Veo 2.0",
            "supports_duration": True,
            "supports_enhance": True,
            "supports_fps": True,
            "supports_aspect_ratio": True,
            "supports_audio": False,
            "default_duration": 5,
            "generation_time": 180,
        },
    }

    @classmethod
    def normalize_model(cls, model: Optional[str]) -> str:
        if not model:
            return cls.DEFAULT_MODEL
        base = model.strip()
        if base.startswith("models/"):
            base = base.replace("models/", "")
        return cls.ALIASES.get(base, base)

    @classmethod
    def to_daydreams_model(cls, model: Optional[str]) -> Optional[str]:
        normalized = cls.normalize_model(model)
        return cls.DAYDREAMS_MODEL_IDS.get(normalized)

    @classmethod
    def to_daydreams_slug(cls, model: Optional[str]) -> Optional[str]:
        normalized = cls.normalize_model(model)
        slug = cls.DAYDREAMS_SLUGS.get(normalized)
        if slug:
            return slug
        if normalized and "/" in normalized:
            return normalized.split("/")[-1]
        return None

    @classmethod
    def get_config(cls, model: str) -> dict:
        normalized = cls.normalize_model(model)
        return cls.MODELS.get(normalized, cls.MODELS[cls.DEFAULT_MODEL])

    @classmethod
    def build_generation_config(cls, model: str, **kwargs) -> types.GenerateVideosConfig:
        """Build a generation configuration based on model capabilities."""

        normalized = cls.normalize_model(model)
        config = cls.get_config(normalized)

        params = {
            "number_of_videos": kwargs.get("number_of_videos", 1),
        }

        if config["supports_duration"] and "duration_seconds" in kwargs:
            params["duration_seconds"] = kwargs["duration_seconds"]

        if config["supports_enhance"]:
            params["enhance_prompt"] = kwargs.get("enhance_prompt", False)

        if config["supports_fps"] and "fps" in kwargs:
            params["fps"] = kwargs["fps"]

        if config.get("supports_aspect_ratio") and kwargs.get("aspect_ratio"):
            ar = str(kwargs["aspect_ratio"])
            if normalized.startswith("veo-3.0"):
                allowed = {"16:9"}
            elif normalized.startswith("veo-2.0"):
                allowed = {"16:9", "9:16"}
            else:
                allowed = {"16:9"}
            if ar not in allowed:
                raise ValueError(
                    f"aspect_ratio '{ar}' not supported for model '{normalized}'. Allowed: {sorted(allowed)}"
                )
            params["aspect_ratio"] = ar

        if kwargs.get("negative_prompt"):
            params["negative_prompt"] = kwargs["negative_prompt"]

        if kwargs.get("person_generation"):
            params["person_generation"] = kwargs["person_generation"]

        safety_settings = kwargs.get("safety_settings")
        if safety_settings:
            normalized_settings: list = []
            for item in safety_settings:
                try:
                    if hasattr(item, "category") and hasattr(item, "threshold"):
                        normalized_settings.append(item)
                    elif isinstance(item, dict):
                        normalized_settings.append(
                            types.SafetySetting(
                                category=item.get("category"),
                                threshold=item.get("threshold"),
                            )
                        )
                except Exception:
                    continue
            if normalized_settings:
                params["safety_settings"] = normalized_settings

        if kwargs.get("cached_content"):
            params["cached_content"] = kwargs["cached_content"]

        try:
            return types.GenerateVideosConfig(**params)
        except TypeError:
            for optional_key in ["safety_settings", "cached_content"]:
                params.pop(optional_key, None)
            return types.GenerateVideosConfig(**params)
