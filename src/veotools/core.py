import os
import logging
from pathlib import Path
from typing import Optional, Callable
from dotenv import load_dotenv
from google import genai
from google.genai import types

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
        if self._client is None:
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                raise ValueError("GEMINI_API_KEY not found in .env file")
            self._client = genai.Client(api_key=api_key)
    
    @property
    def client(self):
        """Get the Google GenAI client instance.
        
        Returns:
            genai.Client: The initialized GenAI client.
        """
        return self._client

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
    """Configuration and capabilities for different Veo video generation models.
    
    This class manages model-specific configurations and builds generation
    configs based on model capabilities. It handles feature availability,
    parameter validation, and safety settings.
    
    Attributes:
        MODELS: Dictionary of available models and their configurations.
    """
    MODELS = {
        "veo-3.0-fast-generate-preview": {
            "name": "Veo 3.0 Fast",
            "supports_duration": False,
            "supports_enhance": False,
            "supports_fps": False,
            "supports_aspect_ratio": True,
            "supports_audio": True,
            "default_duration": 8,
            "generation_time": 60
        },
        "veo-3.0-generate-preview": {
            "name": "Veo 3.0",
            "supports_duration": False,
            "supports_enhance": False,
            "supports_fps": False,
            "supports_aspect_ratio": True,
            "supports_audio": True,
            "default_duration": 8,
            "generation_time": 120
        },
        "veo-2.0-generate-001": {
            "name": "Veo 2.0",
            "supports_duration": True,
            "supports_enhance": True,
            "supports_fps": True,
            "supports_aspect_ratio": True,
            "supports_audio": False,
            "default_duration": 5,
            "generation_time": 180
        }
    }
    
    @classmethod
    def get_config(cls, model: str) -> dict:
        """Get configuration for a specific model.
        
        Args:
            model: Model identifier (with or without "models/" prefix).
            
        Returns:
            dict: Model configuration dictionary containing capabilities and defaults.
            
        Examples:
            >>> config = ModelConfig.get_config("veo-3.0-fast-generate-preview")
            >>> print(config["name"])  # "Veo 3.0 Fast"
            >>> print(config["supports_duration"])  # False
        """
        if model.startswith("models/"):
            model = model.replace("models/", "")
        
        return cls.MODELS.get(model, cls.MODELS["veo-3.0-fast-generate-preview"])
    
    @classmethod
    def build_generation_config(cls, model: str, **kwargs) -> types.GenerateVideosConfig:
        """Build a generation configuration based on model capabilities.
        
        This method creates a GenerateVideosConfig object with parameters
        appropriate for the specified model. It validates parameters against
        model capabilities and handles safety settings.
        
        Args:
            model: Model identifier to use for generation.
            **kwargs: Generation parameters including:
                - number_of_videos: Number of videos to generate (default: 1)
                - duration_seconds: Video duration (if supported by model)
                - enhance_prompt: Whether to enhance the prompt (if supported)
                - fps: Frames per second (if supported)
                - aspect_ratio: Video aspect ratio (e.g., "16:9")
                - negative_prompt: Negative prompt for generation
                - person_generation: Person generation setting
                - safety_settings: List of safety settings
                - cached_content: Cached content handle
        
        Returns:
            types.GenerateVideosConfig: Configuration object for video generation.
            
        Raises:
            ValueError: If aspect_ratio is not supported by the model.
            
        Examples:
            >>> config = ModelConfig.build_generation_config(
            ...     "veo-3.0-fast-generate-preview",
            ...     number_of_videos=2,
            ...     aspect_ratio="16:9"
            ... )
        """
        config = cls.get_config(model)
        
        params = {
            "number_of_videos": kwargs.get("number_of_videos", 1)
        }
        
        if config["supports_duration"] and "duration_seconds" in kwargs:
            params["duration_seconds"] = kwargs["duration_seconds"]
        
        if config["supports_enhance"]:
            params["enhance_prompt"] = kwargs.get("enhance_prompt", False)
        
        if config["supports_fps"] and "fps" in kwargs:
            params["fps"] = kwargs["fps"]

        # Aspect ratio (e.g., "16:9"; Veo 3 limited to 16:9; Veo 2 supports 16:9 and 9:16)
        if config.get("supports_aspect_ratio") and "aspect_ratio" in kwargs and kwargs["aspect_ratio"]:
            ar = str(kwargs["aspect_ratio"])  # normalize
            model_key = model.replace("models/", "")
            if model_key.startswith("veo-3.0"):
                allowed = {"16:9"}
            elif model_key.startswith("veo-2.0"):
                allowed = {"16:9", "9:16"}
            else:
                allowed = {"16:9"}
            if ar not in allowed:
                raise ValueError(f"aspect_ratio '{ar}' not supported for model '{model_key}'. Allowed: {sorted(allowed)}")
            params["aspect_ratio"] = ar

        # Docs-backed pass-throughs
        if "negative_prompt" in kwargs and kwargs["negative_prompt"]:
            params["negative_prompt"] = kwargs["negative_prompt"]

        if "person_generation" in kwargs and kwargs["person_generation"]:
            # Person generation options vary by model/region; pass through as provided
            params["person_generation"] = kwargs["person_generation"]
        
        # Safety settings (optional, SDK >= 1.30.0 for some modalities). Accept either
        # a list of dicts {category, threshold} or already-constructed types.SafetySetting.
        safety_settings = kwargs.get("safety_settings")
        if safety_settings:
            normalized: list = []
            for item in safety_settings:
                try:
                    if hasattr(item, "category") and hasattr(item, "threshold"):
                        normalized.append(item)
                    elif isinstance(item, dict):
                        normalized.append(types.SafetySetting(
                            category=item.get("category"),
                            threshold=item.get("threshold"),
                        ))
                except Exception:
                    # Ignore malformed entries
                    continue
            if normalized:
                params["safety_settings"] = normalized

        # Cached content handle (best-effort pass-through if supported)
        if "cached_content" in kwargs and kwargs["cached_content"]:
            params["cached_content"] = kwargs["cached_content"]
        
        # Construct config, dropping unknown fields if the SDK doesn't support them
        try:
            return types.GenerateVideosConfig(**params)
        except TypeError:
            # Remove optional fields that may not be recognized by this client version
            for optional_key in ["safety_settings", "cached_content"]:
                params.pop(optional_key, None)
            return types.GenerateVideosConfig(**params)