"""Video generation functions for Veo Tools."""

import time
import re
import logging
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


def _apply_default_person_generation(
    model: str,
    mode: str,
    config_params: dict,
) -> None:
    """Populate default person_generation for Veo 3 models when unspecified."""

    if "person_generation" in config_params and config_params["person_generation"]:
        return

    model_key = model.replace("models/", "") if model else ""
    if model_key.startswith("veo-3."):
        if mode == "text":
            config_params["person_generation"] = "allow_all"
        else:  # image or video
            config_params["person_generation"] = "allow_adult"

def generate_from_text(
    prompt: str,
    model: str = "veo-3.0-fast-generate-preview",
    duration_seconds: Optional[int] = None,
    on_progress: Optional[Callable] = None,
    **kwargs,
) -> VideoResult:
    """Generate a video from a text prompt.

    Automatically selects the active video provider (Google GenAI or Daydreams Router)
    based on configuration. Falls back to Google behaviour when no provider override
    is specified.
    """

    veo_client = VeoClient()
    if veo_client.provider == "daydreams":
        return _generate_from_text_daydreams(
            veo_client.client,
            prompt,
            model=model,
            duration_seconds=duration_seconds,
            on_progress=on_progress,
            **kwargs,
        )

    return _generate_from_text_google(
        veo_client.client,
        prompt,
        model=model,
        duration_seconds=duration_seconds,
        on_progress=on_progress,
        **kwargs,
    )


def _generate_from_text_google(
    client,
    prompt: str,
    *,
    model: str,
    duration_seconds: Optional[int],
    on_progress: Optional[Callable],
    **kwargs,
) -> VideoResult:
    storage = StorageManager()
    progress = ProgressTracker(on_progress)
    result = VideoResult()

    normalized_model = ModelConfig.normalize_model(model)
    sdk_model = f"models/{normalized_model}"

    result.prompt = prompt
    result.model = normalized_model

    try:
        progress.start("Initializing")

        config_params = kwargs.copy()
        if duration_seconds:
            config_params["duration_seconds"] = duration_seconds

        _apply_default_person_generation(sdk_model, "text", config_params)
        _validate_person_generation(sdk_model, "text", config_params.get("person_generation"))

        config = ModelConfig.build_generation_config(normalized_model, **config_params)

        progress.update("Submitting", 10)
        operation = client.models.generate_videos(
            model=sdk_model,
            prompt=prompt,
            config=config,
        )

        result.operation_id = operation.name

        model_info = ModelConfig.get_config(normalized_model)
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
                    duration=model_info["default_duration"],
                )

            progress.complete("Complete")
            result.update_progress("Complete", 100)
        else:
            raise RuntimeError("Video generation failed")

    except Exception as exc:
        result.mark_failed(exc)
        raise

    return result


def _generate_from_text_daydreams(
    client,
    prompt: str,
    *,
    model: str,
    duration_seconds: Optional[int],
    on_progress: Optional[Callable],
    **kwargs,
) -> VideoResult:
    storage = StorageManager()
    progress = ProgressTracker(on_progress)
    result = VideoResult()

    normalized_model = ModelConfig.normalize_model(model)
    router_model = (
        ModelConfig.to_daydreams_model(normalized_model)
        or ModelConfig.to_daydreams_model(model)
        or model
    )
    router_slug = (
        ModelConfig.to_daydreams_slug(normalized_model)
        or ModelConfig.to_daydreams_slug(model)
    )

    if not router_model:
        raise ValueError(f"Model '{model}' is not supported by Daydreams Router")

    result.prompt = prompt
    result.model = router_model

    poll_interval = max(int(kwargs.get("poll_interval", 5)), 2)
    status_progress = {"queued": 5, "processing": 55}

    try:
        progress.start("Submitting")

        config = ModelConfig.get_config(normalized_model)

        payload: dict = {"prompt": prompt}

        requested_duration = duration_seconds or kwargs.get("duration_seconds")
        if requested_duration:
            payload["duration_seconds"] = int(requested_duration)
        elif config.get("default_duration"):
            payload["duration_seconds"] = int(config["default_duration"])

        if kwargs.get("aspect_ratio"):
            payload["aspect_ratio"] = kwargs["aspect_ratio"]
        if kwargs.get("resolution"):
            payload["resolution"] = kwargs["resolution"]

        if kwargs.get("enable_audio") is not None:
            payload["enable_audio"] = bool(kwargs["enable_audio"])
        elif kwargs.get("audio") is not None:
            payload["enable_audio"] = bool(kwargs["audio"])

        if kwargs.get("webhook_url"):
            payload["webhook_url"] = kwargs["webhook_url"]
        if kwargs.get("user"):
            payload["user"] = kwargs["user"]

        logging.getLogger(__name__).info(
            "daydreams: submitting text job model=%s duration=%s options=%s",
            router_model,
            payload.get("duration_seconds"),
            {k: v for k, v in payload.items() if k not in {"prompt"}},
        )

        job = client.submit_video_job(router_model, payload, slug=router_slug)
        job_id = job.get("job_id") or job.get("id")
        if not job_id:
            raise RuntimeError("Daydreams Router did not return a job identifier")

        result.operation_id = job_id

        status = job.get("status", "queued")
        logging.getLogger(__name__).info(
            "daydreams: job accepted id=%s status=%s status_url=%s",
            job_id,
            status,
            job.get("status_url"),
        )
        progress.update(status.capitalize(), status_progress.get(status, 5))
        result.update_progress(status.capitalize(), status_progress.get(status, 5))

        while status in ("queued", "processing"):
            time.sleep(poll_interval)
            job = client.get_video_job(job_id)
            status = job.get("status", status)
            logging.getLogger(__name__).info(
                "daydreams: job %s heartbeat status=%s", job_id, status
            )
            progress.update(status.capitalize(), status_progress.get(status, 60))
            result.update_progress(status.capitalize(), status_progress.get(status, 60))

        if status != "succeeded":
            error_message = job.get("error") or f"Video generation failed with status '{status}'"
            logging.getLogger(__name__).error(
                "daydreams: job %s failed status=%s error=%s",
                job_id,
                status,
                error_message,
            )
            raise RuntimeError(error_message)

        assets = job.get("assets", []) or []
        if not assets:
            status_url = job.get("status_url")
            if status_url and hasattr(client, "fetch_job_status"):
                refreshed = client.fetch_job_status(status_url)
                logging.getLogger(__name__).info(
                    "daydreams: job %s refreshed via status_url assets=%s",
                    job_id,
                    len(refreshed.get("assets", []) or []),
                )
                assets = refreshed.get("assets", []) or []
            if not assets:
                refreshed = client.get_video_job(job_id)
                logging.getLogger(__name__).info(
                    "daydreams: job %s refreshed via GET assets=%s",
                    job_id,
                    len(refreshed.get("assets", []) or []),
                )
                assets = refreshed.get("assets", []) or []
        video_asset = next(
            (
                asset
                for asset in assets
                if "video" in (asset.get("mime_type") or "")
                or (asset.get("url") or "").endswith(".mp4")
            ),
            None,
        )

        if not video_asset or not video_asset.get("url"):
            raise RuntimeError("Video generation succeeded but no downloadable asset was returned")

        progress.update("Downloading", 95)
        download_path = storage.get_video_path(f"video_{result.id[:8]}.mp4")
        client.download_asset(video_asset["url"], download_path)

        result.path = download_path
        result.url = storage.get_url(download_path)

        try:
            info = get_video_info(download_path)
            result.metadata = VideoMetadata(
                fps=float(info.get("fps", 24.0)),
                duration=float(info.get("duration", payload.get("duration_seconds", config.get("default_duration", 0)))),
                width=int(info.get("width", 0)),
                height=int(info.get("height", 0)),
            )
        except Exception:
            result.metadata = VideoMetadata(
                fps=24.0,
                duration=float(payload.get("duration_seconds", config.get("default_duration", 0) or 0)),
            )

        progress.complete("Complete")
        logging.getLogger(__name__).info(
            "daydreams: job %s complete asset=%s", job_id, video_asset
        )
        result.update_progress("Complete", 100)

    except Exception as exc:
        logging.getLogger(__name__).exception(
            "daydreams: job %s errored", result.operation_id
        )
        result.mark_failed(exc)
        raise

    return result


def generate_from_image(
    image_path: Path,
    prompt: str,
    model: str = "veo-3.0-fast-generate-preview",
    on_progress: Optional[Callable] = None,
    **kwargs,
) -> VideoResult:
    """Generate a video from an image seed."""

    veo_client = VeoClient()
    if veo_client.provider == "daydreams":
        raise NotImplementedError(
            "Daydreams Router provider does not currently support image-to-video generation in veotools"
        )

    return _generate_from_image_google(
        veo_client.client,
        image_path,
        prompt,
        model=model,
        on_progress=on_progress,
        **kwargs,
    )


def _generate_from_image_google(
    client,
    image_path: Path,
    prompt: str,
    *,
    model: str,
    on_progress: Optional[Callable],
    **kwargs,
) -> VideoResult:
    storage = StorageManager()
    progress = ProgressTracker(on_progress)
    result = VideoResult()

    normalized_model = ModelConfig.normalize_model(model)
    sdk_model = f"models/{normalized_model}"

    result.prompt = f"[Image: {image_path.name}] {prompt}"
    result.model = normalized_model

    try:
        progress.start("Loading")

        image = types.Image.from_file(location=str(image_path))

        config_params = kwargs.copy()
        _apply_default_person_generation(sdk_model, "image", config_params)
        _validate_person_generation(sdk_model, "image", config_params.get("person_generation"))

        config = ModelConfig.build_generation_config(normalized_model, **config_params)

        progress.update("Submitting", 10)
        operation = client.models.generate_videos(
            model=sdk_model,
            prompt=prompt,
            image=image,
            config=config,
        )

        result.operation_id = operation.name

        model_info = ModelConfig.get_config(normalized_model)
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
                    duration=model_info["default_duration"],
                )

            progress.complete("Complete")
            result.update_progress("Complete", 100)
        else:
            error_msg = "Video generation failed"
            if hasattr(operation, "error") and operation.error:
                if isinstance(operation.error, dict):
                    error_msg = f"Video generation failed: {operation.error.get('message', str(operation.error))}"
                else:
                    error_msg = f"Video generation failed: {getattr(operation.error, 'message', str(operation.error))}"
            elif hasattr(operation, "response"):
                error_msg = f"Video generation failed: No videos in response (operation: {operation.name})"
            else:
                error_msg = f"Video generation failed: No response from API (operation: {operation.name})"
            raise RuntimeError(error_msg)

    except Exception as exc:
        result.mark_failed(exc)
        raise

    return result


def generate_from_video(
    video_path: Path,
    prompt: str,
    extract_at: float = -1.0,
    model: str = "veo-3.0-fast-generate-preview",
    on_progress: Optional[Callable] = None,
    **kwargs,
) -> VideoResult:
    """Generate a video continuation from an existing clip."""

    veo_client = VeoClient()
    if veo_client.provider == "daydreams":
        raise NotImplementedError(
            "Daydreams Router provider does not currently support video-seeded continuation in veotools"
        )

    return _generate_from_video_google(
        veo_client.client,
        video_path,
        prompt,
        extract_at=extract_at,
        model=model,
        on_progress=on_progress,
        **kwargs,
    )


def _generate_from_video_google(
    client,
    video_path: Path,
    prompt: str,
    *,
    extract_at: float,
    model: str,
    on_progress: Optional[Callable],
    **kwargs,
) -> VideoResult:
    storage = StorageManager()
    progress = ProgressTracker(on_progress)
    result = VideoResult()

    normalized_model = ModelConfig.normalize_model(model)
    sdk_model = f"models/{normalized_model}"

    result.prompt = f"[Video: {video_path.name}] {prompt}"
    result.model = normalized_model

    try:
        progress.start("Extracting frame")

        frame_path = extract_frame(video_path, extract_at=extract_at)
        image = types.Image.from_file(location=str(frame_path))

        config_params = kwargs.copy()
        _apply_default_person_generation(sdk_model, "video", config_params)
        _validate_person_generation(sdk_model, "video", config_params.get("person_generation"))

        config = ModelConfig.build_generation_config(normalized_model, **config_params)

        progress.update("Submitting", 10)
        operation = client.models.generate_videos(
            model=sdk_model,
            prompt=prompt,
            image=image,
            config=config,
        )

        result.operation_id = operation.name

        model_info = ModelConfig.get_config(normalized_model)
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
            video_path_out = storage.get_video_path(filename)

            _download_video(video, video_path_out, client)

            result.path = video_path_out
            result.url = storage.get_url(video_path_out)

            try:
                info = get_video_info(video_path_out)
                result.metadata = VideoMetadata(
                    fps=float(info.get("fps", 24.0)),
                    duration=float(info.get("duration", model_info["default_duration"])),
                    width=int(info.get("width", 0)),
                    height=int(info.get("height", 0)),
                )
            except Exception:
                result.metadata = VideoMetadata(
                    fps=24.0,
                    duration=model_info["default_duration"],
                )

            progress.complete("Complete")
            result.update_progress("Complete", 100)
        else:
            error_msg = "Video generation failed"
            if hasattr(operation, "error") and operation.error:
                if isinstance(operation.error, dict):
                    error_msg = f"Video generation failed: {operation.error.get('message', str(operation.error))}"
                else:
                    error_msg = f"Video generation failed: {getattr(operation.error, 'message', str(operation.error))}"
            elif hasattr(operation, "response"):
                error_msg = f"Video generation failed: No videos in response (operation: {operation.name})"
            else:
                error_msg = f"Video generation failed: No response from API (operation: {operation.name})"
            raise RuntimeError(error_msg)

    except Exception as exc:
        result.mark_failed(exc)
        raise

    return result


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
