"""MCP-friendly API wrappers for Veo Tools.

This module exposes small, deterministic, JSON-first functions intended for
use in Model Context Protocol (MCP) servers. It builds on top of the existing
blocking SDK functions by providing a non-blocking job lifecycle:

- generate_start(params) -> submits a generation job and returns immediately
- generate_get(job_id) -> fetches job status/progress/result
- generate_cancel(job_id) -> requests cancellation for a running job

It also provides environment/system helpers:
- preflight() -> checks API key, ffmpeg, and filesystem permissions
- version() -> returns package and key dependency versions

Design notes:
- Jobs are persisted as JSON files under StorageManager's base directory
  ("output/ops"). This allows stateless MCP handlers to inspect progress
  and results across processes.
- A background thread runs the blocking generation call and updates job state
  via the JobStore. Cancellation is cooperative: the on_progress callback
  checks a cancel flag in the persisted job state and raises Cancelled.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from ..core import StorageManager, ProgressTracker
from ..generate.video import (
    generate_from_text,
    generate_from_image,
    generate_from_video,
)
from ..core import ModelConfig, VeoClient
from google.genai import types


# ----------------------------
# Exceptions and error codes
# ----------------------------

class Cancelled(Exception):
    """Exception raised to signal cooperative cancellation of a generation job.
    
    This exception is raised internally when a job's cancel_requested flag is set
    to True, allowing for graceful termination of long-running operations.
    """


# Stable error codes for MCP responses
ERROR_CODES = {
    "VEOCONFIG": "Configuration error (e.g., missing API key)",
    "VEOAPI": "Remote API error",
    "DOWNLOAD": "Download error",
    "IO": "Filesystem error",
    "STITCH": "Stitching error",
    "VALIDATION": "Input validation error",
    "CANCELLED": "Operation cancelled",
    "UNKNOWN": "Unknown error",
}


# ----------------------------
# Job persistence
# ----------------------------


@dataclass
class JobRecord:
    """Data class representing a generation job's state and metadata.
    
    Stores all information about a generation job including status, progress,
    parameters, results, and error information. Used for job persistence and
    state management across processes.
    
    Attributes:
        job_id: Unique identifier for the job.
        status: Current job status (pending|processing|complete|failed|cancelled).
        progress: Progress percentage (0-100).
        message: Current status message.
        created_at: Unix timestamp when job was created.
        updated_at: Unix timestamp of last update.
        cancel_requested: Whether cancellation has been requested.
        kind: Generation type (text|image|video).
        params: Dictionary of generation parameters.
        result: Optional result data when job completes.
        error_code: Optional error code if job fails.
        error_message: Optional error description if job fails.
        remote_operation_id: Optional ID from the remote API operation.
    """
    job_id: str
    status: str  # pending | processing | complete | failed | cancelled
    progress: int
    message: str
    created_at: float
    updated_at: float
    cancel_requested: bool
    kind: str  # text | image | video
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    remote_operation_id: Optional[str] = None

    def to_json(self) -> str:
        """Convert the job record to JSON string representation.
        
        Returns:
            str: JSON string representation of the job record.
        """
        return json.dumps(asdict(self), ensure_ascii=False)


class JobStore:
    """File-based persistence layer for generation jobs.

    Manages storage and retrieval of job records using JSON files in the
    filesystem. Each job is stored as a separate JSON file under the
    `output/ops/{job_id}.json` path structure.
    
    This design allows stateless MCP handlers to inspect job progress
    and results across different processes and sessions.
    
    Attributes:
        storage: StorageManager instance for base path management.
        ops_dir: Directory path where job files are stored.
    """

    def __init__(self, storage: Optional[StorageManager] = None):
        """Initialize the job store with optional custom storage manager.
        
        Args:
            storage: Optional StorageManager instance. If None, creates a new one.
        """
        self.storage = storage or StorageManager()
        self.ops_dir = self.storage.base_path / "ops"
        self.ops_dir.mkdir(exist_ok=True)

    def _path(self, job_id: str) -> Path:
        """Get the file system path for a job record.
        
        Args:
            job_id: The unique job identifier.
            
        Returns:
            Path: File system path where the job record should be stored.
        """
        return self.ops_dir / f"{job_id}.json"

    def create(self, record: JobRecord) -> None:
        """Create a new job record on disk.
        
        Args:
            record: JobRecord instance to persist.
            
        Raises:
            OSError: If file creation fails.
        """
        path = self._path(record.job_id)
        path.write_text(record.to_json(), encoding="utf-8")

    def read(self, job_id: str) -> Optional[JobRecord]:
        """Read a job record from disk.
        
        Args:
            job_id: The unique job identifier.
            
        Returns:
            JobRecord: The job record if found, None otherwise.
            
        Raises:
            json.JSONDecodeError: If the stored JSON is invalid.
        """
        path = self._path(job_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return JobRecord(**data)

    def update(self, record: JobRecord, **updates: Any) -> JobRecord:
        """Update a job record with new values and persist to disk.
        
        Args:
            record: The JobRecord instance to update.
            **updates: Key-value pairs of attributes to update.
            
        Returns:
            JobRecord: The updated job record.
            
        Raises:
            OSError: If file write fails.
        """
        for k, v in updates.items():
            setattr(record, k, v)
        record.updated_at = time.time()
        self._path(record.job_id).write_text(record.to_json(), encoding="utf-8")
        return record

    def request_cancel(self, job_id: str) -> Optional[JobRecord]:
        """Request cancellation of a job by setting the cancel flag.
        
        Args:
            job_id: The unique job identifier.
            
        Returns:
            JobRecord: Updated job record if found, None otherwise.
            
        Raises:
            OSError: If file write fails.
        """
        record = self.read(job_id)
        if not record:
            return None
        record.cancel_requested = True
        record.updated_at = time.time()
        self._path(job_id).write_text(record.to_json(), encoding="utf-8")
        return record


# ----------------------------
# System helpers
# ----------------------------


def preflight() -> Dict[str, Any]:
    """Check environment and system prerequisites for video generation.

    Performs comprehensive system checks to ensure all required dependencies
    and configurations are available for successful video generation operations.
    This includes API key validation, FFmpeg availability, and filesystem permissions.

    Returns:
        dict: JSON-serializable dictionary containing:
            - ok (bool): Overall system readiness status
            - gemini_api_key (bool): Whether GEMINI_API_KEY is set
            - ffmpeg (dict): FFmpeg installation status and version info
            - write_permissions (bool): Whether output directory is writable
            - base_path (str): Absolute path to the base output directory

    Examples:
        >>> status = preflight()
        >>> if not status['ok']:
        ...     print("System not ready for generation")
        ...     if not status['gemini_api_key']:
        ...         print("Please set GEMINI_API_KEY environment variable")
        ...     if not status['ffmpeg']['installed']:
        ...         print("Please install FFmpeg for video processing")
        >>> else:
        ...     print(f"System ready! Output directory: {status['base_path']}")

    Note:
        This function is designed to be called before starting any video generation
        operations to ensure the environment is properly configured.
    """
    """Check environment and system prerequisites.

    Returns a JSON-serializable dict with pass/fail details.
    """
    storage = StorageManager()
    base = storage.base_path

    # API key
    api_key_present = bool(os.getenv("GEMINI_API_KEY"))

    # ffmpeg
    ffmpeg_installed = False
    ffmpeg_version = None
    try:
        res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        if res.returncode == 0:
            ffmpeg_installed = True
            first_line = (res.stdout or res.stderr).splitlines()[0] if (res.stdout or res.stderr) else ""
            ffmpeg_version = first_line.strip()
    except FileNotFoundError:
        ffmpeg_installed = False

    # write permissions
    write_permissions = False
    try:
        base.mkdir(exist_ok=True)
        test_file = base / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        write_permissions = True
    except Exception:
        write_permissions = False

    return {
        "ok": api_key_present and write_permissions,
        "gemini_api_key": api_key_present,
        "ffmpeg": {"installed": ffmpeg_installed, "version": ffmpeg_version},
        "write_permissions": write_permissions,
        "base_path": str(base.resolve()),
    }


def version() -> Dict[str, Any]:
    """Report package and dependency versions in a JSON-friendly format.
    
    Collects version information for veotools and its key dependencies,
    providing a comprehensive overview of the current software environment.
    Useful for debugging and support purposes.
    
    Returns:
        dict: Dictionary containing:
            - veotools (str|None): veotools package version
            - dependencies (dict): Versions of key Python packages:
                - google-genai: Google GenerativeAI library version
                - opencv-python: OpenCV library version  
                - requests: HTTP requests library version
                - python-dotenv: Environment file loader version
            - ffmpeg (str|None): FFmpeg version string if available
            
    Examples:
        >>> versions = version()
        >>> print(f"veotools: {versions['veotools']}")
        >>> print(f"Google GenAI: {versions['dependencies']['google-genai']}")
        >>> if versions['ffmpeg']:
        ...     print(f"FFmpeg: {versions['ffmpeg']}")
        >>> else:
        ...     print("FFmpeg not available")
        
    Note:
        Returns None for any package that cannot be found or queried.
        This is expected behavior and not an error condition.
    """
    """Report package and dependency versions in a JSON-friendly format."""
    from importlib.metadata import PackageNotFoundError, version as pkg_version
    import veotools as veo

    def safe_ver(name: str) -> Optional[str]:
        try:
            return pkg_version(name)
        except PackageNotFoundError:
            return None
        except Exception:
            return None

    ffmpeg_info = None
    try:
        res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        if res.returncode == 0:
            ffmpeg_info = (res.stdout or res.stderr).splitlines()[0].strip()
    except Exception:
        ffmpeg_info = None

    return {
        "veotools": getattr(veo, "__version__", None),
        "dependencies": {
            "google-genai": safe_ver("google-genai"),
            "opencv-python": safe_ver("opencv-python"),
            "requests": safe_ver("requests"),
            "python-dotenv": safe_ver("python-dotenv"),
        },
        "ffmpeg": ffmpeg_info,
    }


# ----------------------------
# Generation job lifecycle
# ----------------------------


def _build_job(kind: str, params: Dict[str, Any]) -> JobRecord:
    """Create a new job record with initial values.
    
    Args:
        kind: Type of generation job (text|image|video).
        params: Generation parameters dictionary.
        
    Returns:
        JobRecord: New job record with unique ID and initial status.
    """
    now = time.time()
    return JobRecord(
        job_id=str(uuid4()),
        status="processing",
        progress=0,
        message="queued",
        created_at=now,
        updated_at=now,
        cancel_requested=False,
        kind=kind,
        params=params,
    )


def _validate_generate_inputs(params: Dict[str, Any]) -> None:
    """Validate generation parameters for consistency and file existence.
    
    Args:
        params: Generation parameters to validate.
        
    Raises:
        ValueError: If prompt is missing/invalid or multiple input types specified.
        FileNotFoundError: If specified input files don't exist.
    """
    prompt = params.get("prompt")
    img = params.get("input_image_path")
    vid = params.get("input_video_path")

    if not prompt or not isinstance(prompt, str):
        raise ValueError("prompt is required and must be a string")

    modes = sum(bool(x) for x in [img, vid])
    if modes > 1:
        raise ValueError("Provide only one of input_image_path or input_video_path")

    if img and not Path(img).exists():
        raise FileNotFoundError(f"Image not found: {img}")
    if vid and not Path(vid).exists():
        raise FileNotFoundError(f"Video not found: {vid}")


def generate_start(params: Dict[str, Any]) -> Dict[str, Any]:
    """Start a video generation job and return immediately with job details.

    Initiates a video generation job in the background and returns immediately
    with job tracking information. The actual generation runs asynchronously
    and can be monitored using generate_get().

    Args:
        params: Generation parameters dictionary containing:
            - prompt (str): Required text description for generation
            - model (str, optional): Model to use (defaults to veo-3.0-fast-generate-preview)
            - input_image_path (str, optional): Path to input image for image-to-video
            - input_video_path (str, optional): Path to input video for continuation
            - extract_at (float, optional): Time offset for video continuation
            - options (dict, optional): Additional model-specific options

    Returns:
        dict: Job information containing:
            - job_id (str): Unique job identifier for tracking
            - status (str): Initial job status ("processing")
            - progress (int): Initial progress (0)
            - message (str): Status message
            - kind (str): Generation type (text|image|video)
            - created_at (float): Job creation timestamp

    Raises:
        ValueError: If required parameters are missing or invalid.
        FileNotFoundError: If input media files don't exist.

    Examples:
        Start text-to-video generation:
        >>> job = generate_start({"prompt": "A sunset over mountains"})
        >>> print(f"Job started: {job['job_id']}")

        Start image-to-video generation:
        >>> job = generate_start({
        ...     "prompt": "The person starts walking",
        ...     "input_image_path": "photo.jpg"
        ... })

        Start video continuation:
        >>> job = generate_start({
        ...     "prompt": "The action continues",
        ...     "input_video_path": "scene1.mp4",
        ...     "extract_at": -2.0
        ... })

        Start with custom model and options:
        >>> job = generate_start({
        ...     "prompt": "A dancing robot",
        ...     "model": "veo-2.0",
        ...     "options": {"duration_seconds": 10, "enhance": True}
        ... })

    Note:
        The job runs in a background thread. Use generate_get() to check
        progress and retrieve results when complete.
    """
    """Start a generation job and return immediately.

    Expected params keys:
      - prompt: str (required)
      - model: str (optional; default used by underlying SDK)
      - input_image_path: str (optional)
      - input_video_path: str (optional)
      - extract_at: float (optional; for video continuation)
      - options: dict (optional; forwarded to SDK functions)
    """
    _validate_generate_inputs(params)

    kind = "text"
    if params.get("input_image_path"):
        kind = "image"
    elif params.get("input_video_path"):
        kind = "video"

    store = JobStore()
    record = _build_job(kind, params)
    store.create(record)

    # Start background worker
    worker = threading.Thread(target=_run_generation, args=(record.job_id,), daemon=True)
    worker.start()

    return {
        "job_id": record.job_id,
        "status": record.status,
        "progress": record.progress,
        "message": record.message,
        "kind": record.kind,
        "created_at": record.created_at,
    }


def generate_get(job_id: str) -> Dict[str, Any]:
    """Get the current status and results of a generation job.

    Retrieves the current state of a generation job including progress,
    status, and results if complete. This function can be called repeatedly
    to monitor job progress.

    Args:
        job_id: The unique job identifier returned by generate_start().

    Returns:
        dict: Job status information containing:
            - job_id (str): The job identifier
            - status (str): Current status (processing|complete|failed|cancelled)
            - progress (int): Progress percentage (0-100)
            - message (str): Current status message
            - kind (str): Generation type (text|image|video)
            - remote_operation_id (str|None): Remote API operation ID if available
            - updated_at (float): Last update timestamp
            - result (dict, optional): Generation results when status is "complete"
            - error_code (str, optional): Error code if status is "failed"
            - error_message (str, optional): Error description if status is "failed"

        If job_id is not found, returns:
            - error_code (str): "VALIDATION"
            - error_message (str): Error description

    Examples:
        Check job progress:
        >>> status = generate_get(job_id)
        >>> print(f"Progress: {status['progress']}% - {status['message']}")

        Wait for completion:
        >>> import time
        >>> while True:
        ...     status = generate_get(job_id)
        ...     if status['status'] == 'complete':
        ...         print(f"Video ready: {status['result']['path']}")
        ...         break
        ...     elif status['status'] == 'failed':
        ...         print(f"Generation failed: {status['error_message']}")
        ...         break
        ...     time.sleep(5)

        Handle different outcomes:
        >>> status = generate_get(job_id)
        >>> if status['status'] == 'complete':
        ...     video_path = status['result']['path']
        ...     metadata = status['result']['metadata']
        ...     print(f"Success! Video: {video_path}")
        ...     print(f"Duration: {metadata['duration']}s")
        ... elif status['status'] == 'failed':
        ...     print(f"Error ({status['error_code']}): {status['error_message']}")
        ... else:
        ...     print(f"Still processing: {status['progress']}%")
    """
    """Get the current status of a generation job."""
    store = JobStore()
    record = store.read(job_id)
    if not record:
        return {"error_code": "VALIDATION", "error_message": f"job_id not found: {job_id}"}

    payload: Dict[str, Any] = {
        "job_id": record.job_id,
        "status": record.status,
        "progress": record.progress,
        "message": record.message,
        "kind": record.kind,
        "remote_operation_id": record.remote_operation_id,
        "updated_at": record.updated_at,
    }
    if record.result:
        payload["result"] = record.result
    if record.error_code:
        payload["error_code"] = record.error_code
        payload["error_message"] = record.error_message
    return payload


def generate_cancel(job_id: str) -> Dict[str, Any]:
    """Request cancellation of a running generation job.

    Attempts to cancel a generation job that is currently processing.
    Cancellation is cooperative - the job will stop at the next progress
    update checkpoint. Already completed or failed jobs cannot be cancelled.

    Args:
        job_id: The unique job identifier to cancel.

    Returns:
        dict: Cancellation response containing:
            - job_id (str): The job identifier
            - status (str): "cancelling" if request was accepted

        If job_id is not found, returns:
            - error_code (str): "VALIDATION"
            - error_message (str): Error description

    Examples:
        Cancel a running job:
        >>> response = generate_cancel(job_id)
        >>> if 'error_code' not in response:
        ...     print(f"Cancellation requested for job {response['job_id']}")
        ... else:
        ...     print(f"Cancel failed: {response['error_message']}")

        Check if cancellation succeeded:
        >>> generate_cancel(job_id)
        >>> time.sleep(2)
        >>> status = generate_get(job_id)
        >>> if status['status'] == 'cancelled':
        ...     print("Job successfully cancelled")

    Note:
        Cancellation may not be immediate - the job will stop at the next
        progress checkpoint. Monitor with generate_get() to confirm cancellation.
    """
    """Request cancellation of a running generation job."""
    store = JobStore()
    record = store.request_cancel(job_id)
    if not record:
        return {"error_code": "VALIDATION", "error_message": f"job_id not found: {job_id}"}
    return {"job_id": job_id, "status": "cancelling"}


def _run_generation(job_id: str) -> None:
    """Background worker function that runs the actual generation process.
    
    This function runs in a separate thread and handles the entire generation
    lifecycle including progress reporting, cooperative cancellation, and
    error handling. Updates job state throughout the process.
    
    Args:
        job_id: The unique job identifier to process.
        
    Note:
        This is an internal function called by the background thread system.
        It should not be called directly.
    """
    """Background worker: runs the blocking generation and updates job state."""
    store = JobStore()
    record = store.read(job_id)
    if not record:
        return

    # Progress reporter that also checks for cooperative cancellation
    def _on_progress(message: str, percent: int):
        # Reload to read latest cancel flag
        current = store.read(job_id)
        if not current:
            return
        if current.cancel_requested:
            raise Cancelled()
        store.update(current, message=message, progress=int(percent), status="processing")

    try:
        prompt: str = record.params.get("prompt")
        model: Optional[str] = record.params.get("model")
        options: Dict[str, Any] = record.params.get("options") or {}

        result_dict: Dict[str, Any]

        if record.kind == "text":
            res = generate_from_text(prompt, model=model or "veo-3.0-fast-generate-preview", on_progress=_on_progress, **options)
            result_dict = res.to_dict()
            remote_op_id = res.operation_id
        elif record.kind == "image":
            img_path = Path(record.params["input_image_path"])  # validated earlier
            res = generate_from_image(img_path, prompt, model=model or "veo-3.0-fast-generate-preview", on_progress=_on_progress, **options)
            result_dict = res.to_dict()
            remote_op_id = res.operation_id
        else:  # video
            vid_path = Path(record.params["input_video_path"])  # validated earlier
            extract_at = record.params.get("extract_at", -1.0)
            res = generate_from_video(vid_path, prompt, extract_at=extract_at, model=model or "veo-3.0-fast-generate-preview", on_progress=_on_progress, **options)
            result_dict = res.to_dict()
            remote_op_id = res.operation_id

        # Mark complete
        current = store.read(job_id) or record
        store.update(
            current,
            status="complete",
            progress=100,
            message="Complete",
            result=_sanitize_result(result_dict),
            remote_operation_id=remote_op_id,
        )

    except Cancelled:
        current = store.read(job_id) or record
        store.update(current, status="cancelled", message="Cancelled by request")
    except FileNotFoundError as e:
        current = store.read(job_id) or record
        store.update(current, status="failed", error_code="IO", error_message=str(e), message="IO error")
    except ValueError as e:
        current = store.read(job_id) or record
        store.update(current, status="failed", error_code="VALIDATION", error_message=str(e), message="Validation error")
    except Exception as e:
        # Unknown or API error; attempt to classify a bit
        msg = str(e)
        code = "VEOAPI" if "Video generation" in msg or "google" in msg.lower() else "UNKNOWN"
        current = store.read(job_id) or record
        store.update(current, status="failed", error_code=code, error_message=msg, message="Failed")


def _sanitize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure result dictionary is JSON-serializable with proper types.
    
    Args:
        result: Result dictionary to sanitize.
        
    Returns:
        dict: Sanitized result with Path objects converted to strings.
    """
    """Ensure result dict is JSON-serializable and paths are strings."""
    out: Dict[str, Any] = dict(result)
    # Normalize path types
    if out.get("path") is not None:
        out["path"] = str(out["path"])
    # Nested metadata should already be primitives via to_dict(), but be defensive
    if isinstance(out.get("metadata"), dict):
        meta = out["metadata"]
        out["metadata"] = {k: (str(v) if isinstance(v, Path) else v) for k, v in meta.items()}
    return out


# ----------------------------
# Public MCP-friendly surface
# ----------------------------

__all__ = [
    "preflight",
    "version",
    "list_models",
    "generate_start",
    "generate_get",
    "generate_cancel",
    "cache_create_from_files",
    "cache_get",
    "cache_list",
    "cache_update",
    "cache_delete",
]


def list_models(include_remote: bool = True) -> Dict[str, Any]:
    """List available video generation models with their capabilities.

    Retrieves information about available Veo models including their capabilities,
    default settings, and performance characteristics. Combines static model
    registry with optional remote model discovery.

    Args:
        include_remote: Whether to include models discovered from the remote API.
            If True, attempts to fetch additional model information from Google's API.
            If False, returns only the static model registry. Defaults to True.

    Returns:
        dict: Model information containing:
            - models (list): List of model dictionaries, each containing:
                - id (str): Model identifier (e.g., "veo-3.0-fast-generate-preview")
                - name (str): Human-readable model name
                - capabilities (dict): Feature flags:
                    - supports_duration (bool): Can specify custom duration
                    - supports_enhance (bool): Can enhance prompts
                    - supports_fps (bool): Can specify frame rate
                    - supports_audio (bool): Can generate audio
                - default_duration (float|None): Default video duration in seconds
                - generation_time (float|None): Estimated generation time in seconds
                - source (str): Data source ("static", "remote", or "static+remote")

    Examples:
        List all available models:
        >>> models = list_models()
        >>> for model in models['models']:
        ...     print(f"{model['name']} ({model['id']})")
        ...     if model['capabilities']['supports_duration']:
        ...         print(f"  Default duration: {model['default_duration']}s")

        Find models with specific capabilities:
        >>> models = list_models()
        >>> audio_models = [
        ...     m for m in models['models']
        ...     if m['capabilities']['supports_audio']
        ... ]
        >>> print(f"Found {len(audio_models)} models with audio support")

        Use only static model registry:
        >>> models = list_models(include_remote=False)
        >>> static_models = [m for m in models['models'] if m['source'] == 'static']

    Note:
        Results are cached for 10 minutes to improve performance. Remote model
        discovery failures are silently ignored - static registry is always available.
    """
    """List available models and capability flags.

    Returns a JSON dict: { models: [ {id, name, capabilities, default_duration, generation_time, source} ] }
    """
    models: Dict[str, Dict[str, Any]] = {}

    # Seed from static registry
    for model_id, cfg in ModelConfig.MODELS.items():
        models[model_id] = {
            "id": model_id,
            "name": cfg.get("name", model_id),
            "capabilities": {
                "supports_duration": cfg.get("supports_duration", False),
                "supports_enhance": cfg.get("supports_enhance", False),
                "supports_fps": cfg.get("supports_fps", False),
                "supports_audio": cfg.get("supports_audio", False),
            },
            "default_duration": cfg.get("default_duration"),
            "generation_time": cfg.get("generation_time"),
            "source": "static",
        }

    # Optionally merge from remote discovery (best-effort)
    if include_remote:
        try:
            client = VeoClient().client
            if hasattr(client, "models") and hasattr(client.models, "list"):
                for remote in client.models.list():
                    # Expect names like "models/veo-3.0-fast-generate-preview"
                    raw_name = getattr(remote, "name", "") or ""
                    model_id = raw_name.replace("models/", "") if raw_name else getattr(remote, "base_model_id", None)
                    if not model_id:
                        continue
                    entry = models.get(model_id, {
                        "id": model_id,
                        "name": getattr(remote, "display_name", model_id),
                        "capabilities": {},
                    })
                    entry["source"] = (entry.get("source") or "") + ("+remote" if entry.get("source") else "remote")
                    models[model_id] = entry
        except Exception:
            # Ignore remote discovery errors; static list is sufficient
            pass

    # Basic cache to disk for 10 minutes
    try:
        store = JobStore()
        cache_path = store.ops_dir / "models.json"
        now = time.time()
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if now - float(cached.get("updated_at", 0)) < 600:
                    # Merge remote source flags if needed, else return cache
                    return cached.get("data", {"models": list(models.values())})
            except Exception:
                pass
        payload = {"models": list(models.values())}
        cache_path.write_text(json.dumps({"updated_at": now, "data": payload}), encoding="utf-8")
        return payload
    except Exception:
        return {"models": list(models.values())}



# ----------------------------
# Caching helpers (best-effort)
# ----------------------------


def cache_create_from_files(model: str, files: list[str], system_instruction: Optional[str] = None) -> Dict[str, Any]:
    """Create a cached content handle from local file paths.

    Uploads local files to create a cached content context that can be reused
    across multiple API calls for efficiency. This is particularly useful when
    working with large files or when making multiple requests with the same context.

    Args:
        model: The model identifier to associate with the cached content.
        files: List of local file paths to upload and cache.
        system_instruction: Optional system instruction to include with the cache.

    Returns:
        dict: Cache creation result containing:
            - name (str): Unique cache identifier for future reference
            - model (str): The associated model identifier
            - system_instruction (str|None): The system instruction if provided
            - contents_count (int): Number of files successfully cached

        On failure, returns:
            - error_code (str): Error classification
            - error_message (str): Detailed error description

    Examples:
        Cache multiple reference images:
        >>> result = cache_create_from_files(
        ...     "veo-3.0-fast-generate-preview",
        ...     ["ref1.jpg", "ref2.jpg", "ref3.jpg"],
        ...     "These are reference images for style consistency"
        ... )
        >>> if 'name' in result:
        ...     cache_name = result['name']
        ...     print(f"Cache created: {cache_name}")
        ... else:
        ...     print(f"Cache creation failed: {result['error_message']}")

        Cache video reference:
        >>> result = cache_create_from_files(
        ...     "veo-2.0",
        ...     ["reference_video.mp4"]
        ... )

    Raises:
        The function catches all exceptions and returns them as error dictionaries
        rather than raising them directly.

    Note:
        Files are uploaded to Google's servers as part of the caching process.
        Ensure you have appropriate permissions for the files and comply with
        Google's usage policies.
    """
    """Create a cached content handle from local file paths.

    Returns { name, model, system_instruction?, contents_count } or { error_code, error_message } on failure.
    """
    try:
        client = VeoClient().client
        uploaded = []
        for f in files:
            p = Path(f)
            if not p.exists():
                return {"error_code": "VALIDATION", "error_message": f"File not found: {f}"}
            uploaded.append(client.files.upload(file=p))
        cfg = types.CreateCachedContentConfig(
            contents=uploaded,
            system_instruction=system_instruction if system_instruction else None,
        )
        cache = client.caches.create(model=model, config=cfg)
        return {
            "name": getattr(cache, "name", None),
            "model": model,
            "system_instruction": system_instruction,
            "contents_count": len(uploaded),
        }
    except Exception as e:
        return {"error_code": "UNKNOWN", "error_message": str(e)}


def cache_get(name: str) -> Dict[str, Any]:
    """Retrieve cached content metadata by cache name.

    Fetches information about a previously created cached content entry,
    including lifecycle information like expiration times and creation dates.

    Args:
        name: The unique cache identifier returned by cache_create_from_files().

    Returns:
        dict: Cache metadata containing:
            - name (str): The cache identifier
            - ttl (str|None): Time-to-live if available
            - expire_time (str|None): Expiration timestamp if available
            - create_time (str|None): Creation timestamp if available

        On failure, returns:
            - error_code (str): Error classification
            - error_message (str): Detailed error description

    Examples:
        Check cache status:
        >>> cache_info = cache_get(cache_name)
        >>> if 'error_code' not in cache_info:
        ...     print(f"Cache {cache_info['name']} is active")
        ...     if cache_info.get('expire_time'):
        ...         print(f"Expires: {cache_info['expire_time']}")
        ... else:
        ...     print(f"Cache not found: {cache_info['error_message']}")

    Note:
        Available metadata fields may vary depending on the Google GenAI
        library version and cache configuration.
    """
    """Retrieve cached content metadata by name.

    Returns minimal metadata; fields vary by library version.
    """
    try:
        client = VeoClient().client
        cache = client.caches.get(name=name)
        out: Dict[str, Any] = {"name": getattr(cache, "name", name)}
        # Attempt to surface lifecycle info when available
        for k in ("ttl", "expire_time", "create_time"):
            v = getattr(cache, k, None)
            if v is not None:
                out[k] = v
        return out
    except Exception as e:
        return {"error_code": "UNKNOWN", "error_message": str(e)}


def cache_list() -> Dict[str, Any]:
    """List all cached content entries with their metadata.

    Retrieves a list of all cached content entries accessible to the current
    API key, including their metadata and lifecycle information.

    Returns:
        dict: Cache listing containing:
            - caches (list): List of cache entries, each containing:
                - name (str): Cache identifier
                - model (str|None): Associated model if available
                - display_name (str|None): Human-readable name if available
                - create_time (str|None): Creation timestamp if available
                - update_time (str|None): Last update timestamp if available
                - expire_time (str|None): Expiration timestamp if available
                - usage_metadata (dict|None): Usage statistics if available

        On failure, returns:
            - error_code (str): Error classification
            - error_message (str): Detailed error description

    Examples:
        List all caches:
        >>> cache_list_result = cache_list()
        >>> if 'caches' in cache_list_result:
        ...     for cache in cache_list_result['caches']:
        ...         print(f"Cache: {cache['name']}")
        ...         if cache.get('model'):
        ...             print(f"  Model: {cache['model']}")
        ...         if cache.get('expire_time'):
        ...             print(f"  Expires: {cache['expire_time']}")
        ... else:
        ...     print(f"Failed to list caches: {cache_list_result['error_message']}")

        Find caches by model:
        >>> result = cache_list()
        >>> if 'caches' in result:
        ...     veo3_caches = [
        ...         c for c in result['caches']
        ...         if c.get('model', '').startswith('veo-3')
        ...     ]

    Note:
        Metadata availability depends on the Google GenAI library version
        and individual cache configurations.
    """
    """List cached content metadata entries.

    Returns { caches: [ {name, model?, display_name?, create_time?, update_time?, expire_time?, usage_metadata?} ] }
    """
    try:
        client = VeoClient().client
        items = []
        for cache in client.caches.list():
            entry: Dict[str, Any] = {"name": getattr(cache, "name", None)}
            for k in ("model", "display_name", "create_time", "update_time", "expire_time", "usage_metadata"):
                v = getattr(cache, k, None)
                if v is not None:
                    entry[k] = v
            items.append(entry)
        return {"caches": items}
    except Exception as e:
        return {"error_code": "UNKNOWN", "error_message": str(e)}


def cache_update(name: str, ttl_seconds: Optional[int] = None, expire_time_iso: Optional[str] = None) -> Dict[str, Any]:
    """Update TTL or expiration time for a cached content entry.

    Modifies the lifecycle settings of an existing cached content entry.
    You can specify either a TTL (time-to-live) in seconds or an absolute
    expiration time, but not both.

    Args:
        name: The unique cache identifier to update.
        ttl_seconds: Optional time-to-live in seconds (e.g., 300 for 5 minutes).
        expire_time_iso: Optional timezone-aware ISO-8601 datetime string
            (e.g., "2024-01-15T10:30:00Z").

    Returns:
        dict: Update result containing:
            - name (str): The cache identifier
            - expire_time (str|None): New expiration time if available
            - ttl (str|None): New TTL setting if available
            - update_time (str|None): Update timestamp if available

        On failure, returns:
            - error_code (str): Error classification
            - error_message (str): Detailed error description

    Examples:
        Extend cache TTL to 1 hour:
        >>> result = cache_update(cache_name, ttl_seconds=3600)
        >>> if 'error_code' not in result:
        ...     print(f"Cache TTL updated: {result.get('ttl')}")
        ... else:
        ...     print(f"Update failed: {result['error_message']}")

        Set specific expiration time:
        >>> result = cache_update(
        ...     cache_name,
        ...     expire_time_iso="2024-12-31T23:59:59Z"
        ... )

        Extend by 30 minutes:
        >>> result = cache_update(cache_name, ttl_seconds=1800)

    Raises:
        Returns error dict instead of raising exceptions directly.

    Note:
        - Only one of ttl_seconds or expire_time_iso should be provided
        - TTL is relative to the current time when the update is processed
        - expire_time_iso should be in UTC timezone for consistency
    """
    """Update TTL or expire_time for a cache (one or the other).

    - ttl_seconds: integer seconds for TTL (e.g., 300)
    - expire_time_iso: timezone-aware ISO-8601 datetime string
    """
    try:
        client = VeoClient().client
        cfg_kwargs: Dict[str, Any] = {}
        if ttl_seconds is not None:
            cfg_kwargs["ttl"] = f"{int(ttl_seconds)}s"
        if expire_time_iso:
            cfg_kwargs["expire_time"] = expire_time_iso
        if not cfg_kwargs:
            return {"error_code": "VALIDATION", "error_message": "Provide ttl_seconds or expire_time_iso"}
        updated = client.caches.update(
            name=name,
            config=types.UpdateCachedContentConfig(**cfg_kwargs),
        )
        out: Dict[str, Any] = {"name": getattr(updated, "name", name)}
        for k in ("expire_time", "ttl", "update_time"):
            v = getattr(updated, k, None)
            if v is not None:
                out[k] = v
        return out
    except Exception as e:
        return {"error_code": "UNKNOWN", "error_message": str(e)}


def cache_delete(name: str) -> Dict[str, Any]:
    """Delete a cached content entry by name.

    Permanently removes a cached content entry and all associated files
    from the system. This action cannot be undone.

    Args:
        name: The unique cache identifier to delete.

    Returns:
        dict: Deletion result containing:
            - deleted (bool): True if deletion was successful
            - name (str): The cache identifier that was deleted

        On failure, returns:
            - error_code (str): Error classification
            - error_message (str): Detailed error description

    Examples:
        Delete a specific cache:
        >>> result = cache_delete(cache_name)
        >>> if result.get('deleted'):
        ...     print(f"Cache {result['name']} deleted successfully")
        ... else:
        ...     print(f"Deletion failed: {result.get('error_message')}")

        Delete with error handling:
        >>> result = cache_delete("non-existent-cache")
        >>> if 'error_code' in result:
        ...     print(f"Error: {result['error_message']}")

    Note:
        Deletion is permanent and cannot be reversed. Ensure you no longer
        need the cached content before calling this function.
    """
    """Delete a cached content entry by name."""
    try:
        client = VeoClient().client
        client.caches.delete(name)
        return {"deleted": True, "name": name}
    except Exception as e:
        return {"error_code": "UNKNOWN", "error_message": str(e)}

