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
    """Validate person_generation per model and mode.

    mode: "text" | "image" | "video" (video treated like image-seeded continuation)
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