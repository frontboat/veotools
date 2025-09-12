"""Video generation functions for Veo Tools."""

import time
import re
import requests
from pathlib import Path
from typing import Optional, Callable
from google.genai import types

from ..core import VeoClient, StorageManager, ProgressTracker, ModelConfig
from ..models import VideoResult, VideoMetadata
from ..process.extractor import extract_frame, get_video_info


def _validate_person_generation(model: str, mode: str, person_generation: Optional[str]) -> None:
    """Validate person_generation parameter based on model and generation mode.

    Validates the person_generation parameter against the constraints defined for different
    Veo model versions and generation modes. Veo 3.0 and 2.0 have different allowed values
    for text vs image/video generation modes.

    Args:
        model: The model identifier (e.g., "veo-3.0-fast-generate-preview").
        mode: Generation mode - "text", "image", or "video" (video treated like image-seeded).
        person_generation: Person generation policy - "allow_all", "allow_adult", or "dont_allow".

    Raises:
        ValueError: If person_generation value is not allowed for the given model and mode.

    Note:
        - Veo 3.0 text mode: allows "allow_all"
        - Veo 3.0 image/video mode: allows "allow_adult"
        - Veo 2.0 text mode: allows "allow_all", "allow_adult", "dont_allow"
        - Veo 2.0 image/video mode: allows "allow_adult", "dont_allow"
    """
    if not person_generation:
        return
    model_key = model.replace("models/", "") if model else ""
    if model_key.startswith("veo-3.0"):
        if mode == "text":
            allowed = {"allow_all"}
        else:  # image or video
            allowed = {"allow_adult"}
    elif model_key.startswith("veo-2.0"):
        if mode == "text":
            allowed = {"allow_all", "allow_adult", "dont_allow"}
        else:  # image or video
            allowed = {"allow_adult", "dont_allow"}
    else:
        # Default to Veo 3 constraints if unknown
        allowed = {"allow_all"} if mode == "text" else {"allow_adult"}
    if person_generation not in allowed:
        raise ValueError(
            f"person_generation='{person_generation}' not allowed for {model_key or 'veo-3.0'} in {mode} mode. Allowed: {sorted(allowed)}"
        )

def generate_from_text(
    prompt: str,
    model: str = "veo-3.0-fast-generate-preview",
    duration_seconds: Optional[int] = None,
    on_progress: Optional[Callable] = None,
    **kwargs
) -> VideoResult:
    """Generate a video from a text prompt using Google's Veo models.

    Creates a video from a text description using the specified Veo model. The function
    handles the entire generation pipeline including job submission, progress tracking,
    video download, and metadata extraction.

    Args:
        prompt: Text description of the video to generate.
        model: Veo model to use for generation. Defaults to "veo-3.0-fast-generate-preview".
        duration_seconds: Desired video duration in seconds. If None, uses model default.
        on_progress: Optional callback function called with progress updates (message, percent).
        **kwargs: Additional generation parameters including:
            - person_generation: Person generation policy ("allow_all", "allow_adult", "dont_allow")
            - enhance: Whether to enhance the prompt
            - fps: Target frames per second
            - audio: Whether to generate audio

    Returns:
        VideoResult: Object containing the generated video path, metadata, and operation details.

    Raises:
        ValueError: If person_generation parameter is invalid for the model/mode combination.
        RuntimeError: If video generation fails or no video is returned.
        FileNotFoundError: If required files are not accessible.

    Examples:
        Generate a simple video:
        >>> result = generate_from_text("A cat playing in a garden")
        >>> print(f"Video saved to: {result.path}")

        Generate with custom duration and progress tracking:
        >>> def progress_handler(message, percent):
        ...     print(f"{message}: {percent}%")
        >>> result = generate_from_text(
        ...     "A sunset over the ocean",
        ...     duration_seconds=10,
        ...     on_progress=progress_handler
        ... )
    """
    client = VeoClient().client
    storage = StorageManager()
    progress = ProgressTracker(on_progress)
    result = VideoResult()
    
    result.prompt = prompt
    result.model = model
    
    try:
        progress.start("Initializing")
        
        if not model.startswith("models/"):
            model = f"models/{model}"
        
        config_params = kwargs.copy()
        if duration_seconds:
            config_params["duration_seconds"] = duration_seconds
        # Validate person_generation constraints (Veo 3/2 rules)
        _validate_person_generation(model, "text", config_params.get("person_generation"))
        
        config = ModelConfig.build_generation_config(
            model.replace("models/", ""),
            **config_params
        )
        
        progress.update("Submitting", 10)
        operation = client.models.generate_videos(
            model=model,
            prompt=prompt,
            config=config
        )
        
        result.operation_id = operation.name
        
        model_info = ModelConfig.get_config(model.replace("models/", ""))
        estimated_time = model_info["generation_time"]
        start_time = time.time()
        
        while not operation.done:
            elapsed = time.time() - start_time
            percent = min(90, int((elapsed / estimated_time) * 80) + 10)
            progress.update(f"Generating {elapsed:.0f}s", percent)
            time.sleep(10)
            operation = client.operations.get(operation)
        
        if operation.response and operation.response.generated_videos:
            video = operation.response.generated_videos[0].video
            
            progress.update("Downloading", 95)
            filename = f"video_{result.id[:8]}.mp4"
            video_path = storage.get_video_path(filename)
            
            _download_video(video, video_path, client)
            
            result.path = video_path
            result.url = storage.get_url(video_path)
            
            # Probe actual metadata from downloaded file
            try:
                info = get_video_info(video_path)
                result.metadata = VideoMetadata(
                    fps=float(info.get("fps", 24.0)),
                    duration=float(info.get("duration", model_info["default_duration"])),
                    width=int(info.get("width", 0)),
                    height=int(info.get("height", 0)),
                )
            except Exception:
                result.metadata = VideoMetadata(
                    fps=24.0,
                    duration=model_info["default_duration"]
                )
            
            progress.complete("Complete")
            result.update_progress("Complete", 100)
            
        else:
            raise RuntimeError("Video generation failed")
            
    except Exception as e:
        result.mark_failed(e)
        raise
    
    return result


def generate_from_image(
    image_path: Path,
    prompt: str,
    model: str = "veo-3.0-fast-generate-preview",
    on_progress: Optional[Callable] = None,
    **kwargs
) -> VideoResult:
    """Generate a video from an image and text prompt using Google's Veo models.

    Creates a video animation starting from a static image, guided by a text prompt.
    The function loads the image, submits the generation job, tracks progress, and
    downloads the resulting video with metadata extraction.

    Args:
        image_path: Path to the input image file (jpg, png, etc.).
        prompt: Text description of how the image should be animated.
        model: Veo model to use for generation. Defaults to "veo-3.0-fast-generate-preview".
        on_progress: Optional callback function called with progress updates (message, percent).
        **kwargs: Additional generation parameters including:
            - person_generation: Person generation policy ("allow_adult", "dont_allow")
            - duration_seconds: Video duration in seconds
            - enhance: Whether to enhance the prompt
            - fps: Target frames per second

    Returns:
        VideoResult: Object containing the generated video path, metadata, and operation details.

    Raises:
        ValueError: If person_generation parameter is invalid for image mode.
        RuntimeError: If video generation fails or the API returns an error.
        FileNotFoundError: If the input image file is not found.

    Examples:
        Animate a static image:
        >>> from pathlib import Path
        >>> result = generate_from_image(
        ...     Path("photo.jpg"),
        ...     "The person starts walking forward"
        ... )
        >>> print(f"Animation saved to: {result.path}")

        Generate with progress tracking:
        >>> def show_progress(msg, pct):
        ...     print(f"{msg}: {pct}%")
        >>> result = generate_from_image(
        ...     Path("landscape.png"),
        ...     "Clouds moving across the sky",
        ...     on_progress=show_progress
        ... )
    """
    client = VeoClient().client
    storage = StorageManager()
    progress = ProgressTracker(on_progress)
    result = VideoResult()
    
    result.prompt = f"[Image: {image_path.name}] {prompt}"
    result.model = model
    
    try:
        progress.start("Loading")
        
        image = types.Image.from_file(location=str(image_path))
        
        if not model.startswith("models/"):
            model = f"models/{model}"
        
        config_params = kwargs.copy()
        # Validate person_generation constraints (Veo 3/2 rules)
        _validate_person_generation(model, "image", config_params.get("person_generation"))
        
        config = ModelConfig.build_generation_config(
            model.replace("models/", ""),
            **config_params
        )
        
        progress.update("Submitting", 10)
        operation = client.models.generate_videos(
            model=model,
            prompt=prompt,
            image=image,
            config=config
        )
        
        result.operation_id = operation.name
        
        model_info = ModelConfig.get_config(model.replace("models/", ""))
        estimated_time = model_info["generation_time"]
        start_time = time.time()
        
        while not operation.done:
            elapsed = time.time() - start_time
            percent = min(90, int((elapsed / estimated_time) * 80) + 10)
            progress.update(f"Generating {elapsed:.0f}s", percent)
            time.sleep(10)
            operation = client.operations.get(operation)
        
        if operation.response and operation.response.generated_videos:
            video = operation.response.generated_videos[0].video
            
            progress.update("Downloading", 95)
            filename = f"video_{result.id[:8]}.mp4"
            video_path = storage.get_video_path(filename)
            
            _download_video(video, video_path, client)
            
            result.path = video_path
            result.url = storage.get_url(video_path)
            # Probe actual metadata from downloaded file
            try:
                info = get_video_info(video_path)
                result.metadata = VideoMetadata(
                    fps=float(info.get("fps", 24.0)),
                    duration=float(info.get("duration", model_info["default_duration"])),
                    width=int(info.get("width", 0)),
                    height=int(info.get("height", 0)),
                )
            except Exception:
                result.metadata = VideoMetadata(
                    fps=24.0,
                    duration=model_info["default_duration"]
                )
            
            progress.complete("Complete")
            result.update_progress("Complete", 100)
            
        else:
            error_msg = "Video generation failed"
            if hasattr(operation, 'error') and operation.error:
                if isinstance(operation.error, dict):
                    error_msg = f"Video generation failed: {operation.error.get('message', str(operation.error))}"
                else:
                    error_msg = f"Video generation failed: {getattr(operation.error, 'message', str(operation.error))}"
            elif hasattr(operation, 'response'):
                error_msg = f"Video generation failed: No videos in response (operation: {operation.name})"
            else:
                error_msg = f"Video generation failed: No response from API (operation: {operation.name})"
            raise RuntimeError(error_msg)
            
    except Exception as e:
        result.mark_failed(e)
        raise
    
    return result


def generate_from_video(
    video_path: Path,
    prompt: str,
    extract_at: float = -1.0,
    model: str = "veo-3.0-fast-generate-preview",
    on_progress: Optional[Callable] = None,
    **kwargs
) -> VideoResult:
    """Generate a video continuation from an existing video using Google's Veo models.

    Creates a new video that continues from a frame extracted from an existing video.
    The function extracts a frame at the specified time offset, then uses it as the
    starting point for generating a continuation guided by the text prompt.

    Args:
        video_path: Path to the input video file.
        prompt: Text description of how the video should continue.
        extract_at: Time offset in seconds for frame extraction. Negative values count
            from the end (e.g., -1.0 extracts 1 second before the end). Defaults to -1.0.
        model: Veo model to use for generation. Defaults to "veo-3.0-fast-generate-preview".
        on_progress: Optional callback function called with progress updates (message, percent).
        **kwargs: Additional generation parameters including:
            - person_generation: Person generation policy ("allow_adult", "dont_allow")
            - duration_seconds: Video duration in seconds
            - enhance: Whether to enhance the prompt
            - fps: Target frames per second

    Returns:
        VideoResult: Object containing the generated video path, metadata, and operation details.

    Raises:
        ValueError: If person_generation parameter is invalid for video continuation mode.
        RuntimeError: If frame extraction fails or video generation fails.
        FileNotFoundError: If the input video file is not found.

    Examples:
        Continue a video from the end:
        >>> result = generate_from_video(
        ...     Path("scene1.mp4"),
        ...     "The character turns around and walks away"
        ... )

        Continue from a specific timestamp:
        >>> result = generate_from_video(
        ...     Path("action.mp4"),
        ...     "The explosion gets bigger",
        ...     extract_at=5.5  # Extract at 5.5 seconds
        ... )

        Continue with progress tracking:
        >>> def track_progress(msg, pct):
        ...     print(f"Progress: {msg} ({pct}%)")
        >>> result = generate_from_video(
        ...     Path("dance.mp4"),
        ...     "The dancer spins faster",
        ...     extract_at=-2.0,
        ...     on_progress=track_progress
        ... )
    """
    progress = ProgressTracker(on_progress)
    storage = StorageManager()
    
    try:
        progress.start("Extracting")
        frame_path = extract_frame(video_path, time_offset=extract_at)
        progress.update("Extracted", 20)
        
        # Validate person_generation constraints for continuation (treat like image)
        if "person_generation" in kwargs:
            _validate_person_generation(model, "video", kwargs.get("person_generation"))

        result = generate_from_image(
            frame_path,
            prompt,
            model=model,
            on_progress=lambda msg, pct: progress.update(msg, 20 + int(pct * 0.8)),
            **kwargs
        )
        
        result.prompt = f"[Continuation of {video_path.name}] {prompt}"
        
        return result
        
    except Exception as e:
        result = VideoResult()
        result.mark_failed(e)
        raise


def _download_video(video: types.Video, output_path: Path, client) -> Path:
    """Download a generated video from Google's API to local storage.

    Downloads video content from either a URI or direct data blob provided by the
    Google GenAI API. Handles authentication headers and writes the video to the
    specified output path.

    Args:
        video: Video object from Google GenAI API containing URI or data.
        output_path: Local path where the video should be saved.
        client: Google GenAI client instance (currently unused but kept for compatibility).

    Returns:
        Path: The output path where the video was saved.

    Raises:
        RuntimeError: If the video object contains neither URI nor data.
        requests.HTTPError: If the download request fails.
        OSError: If writing to the output path fails.

    Note:
        This function requires the GEMINI_API_KEY environment variable to be set
        for URI-based downloads.
    """
    import os
    
    if hasattr(video, 'uri') and video.uri:
        match = re.search(r'/files/([^:]+)', video.uri)
        if match:
            headers = {
                'x-goog-api-key': os.getenv('GEMINI_API_KEY')
            }
            response = requests.get(video.uri, headers=headers)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            return output_path
    
    elif hasattr(video, 'data') and video.data:
        with open(output_path, 'wb') as f:
            f.write(video.data)
        return output_path
    
    else:
        raise RuntimeError("Unable to download video - no URI or data found")