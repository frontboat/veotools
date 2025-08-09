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

from .core import StorageManager, ProgressTracker
from .generate.video import (
    generate_from_text,
    generate_from_image,
    generate_from_video,
)
from .core import ModelConfig, VeoClient


# ----------------------------
# Exceptions and error codes
# ----------------------------

class Cancelled(Exception):
    """Raised internally to signal cooperative cancellation of a job."""


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
        return json.dumps(asdict(self), ensure_ascii=False)


class JobStore:
    """File-based persistence for generation jobs.

    Stores JSON records under `output/ops/{job_id}.json`.
    """

    def __init__(self, storage: Optional[StorageManager] = None):
        self.storage = storage or StorageManager()
        self.ops_dir = self.storage.base_path / "ops"
        self.ops_dir.mkdir(exist_ok=True)

    def _path(self, job_id: str) -> Path:
        return self.ops_dir / f"{job_id}.json"

    def create(self, record: JobRecord) -> None:
        path = self._path(record.job_id)
        path.write_text(record.to_json(), encoding="utf-8")

    def read(self, job_id: str) -> Optional[JobRecord]:
        path = self._path(job_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return JobRecord(**data)

    def update(self, record: JobRecord, **updates: Any) -> JobRecord:
        for k, v in updates.items():
            setattr(record, k, v)
        record.updated_at = time.time()
        self._path(record.job_id).write_text(record.to_json(), encoding="utf-8")
        return record

    def request_cancel(self, job_id: str) -> Optional[JobRecord]:
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
    """Report package and dependency versions in a JSON-friendly format."""
    from importlib.metadata import PackageNotFoundError, version as pkg_version
    import veo_tools as veo

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
        "veo_tools": getattr(veo, "__version__", None),
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
    """Request cancellation of a running generation job."""
    store = JobStore()
    record = store.request_cancel(job_id)
    if not record:
        return {"error_code": "VALIDATION", "error_message": f"job_id not found: {job_id}"}
    return {"job_id": job_id, "status": "cancelling"}


def _run_generation(job_id: str) -> None:
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
]


def list_models(include_remote: bool = True) -> Dict[str, Any]:
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


