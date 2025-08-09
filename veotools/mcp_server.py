"""Built-in MCP server entry point for Veotools.

Run:
  veo-mcp            # via console script
  python -m veotools.mcp_server
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict

from mcp.server.fastmcp import FastMCP, Context
import veotools as veo
from veotools.process.extractor import get_video_info
from veotools.mcp_api import JobStore


app = FastMCP("veotools")


@app.tool()
def preflight() -> dict:
    """Check environment and system prerequisites.

    Returns a JSON dict with: ok, gemini_api_key, ffmpeg {installed, version},
    write_permissions, base_path.
    """
    return veo.preflight()


@app.tool()
def version() -> dict:
    """Report package and dependency versions.

    Returns keys: veotools, dependencies {google-genai, opencv-python, ...}, ffmpeg.
    """
    return veo.version()


@app.tool()
def list_models(include_remote: bool = True) -> dict:
    """List available models with capability flags.

    - include_remote: when true, merges remote discovery from the API.
    Returns { models: [ {id, name, capabilities, default_duration, generation_time, source} ] }.
    """
    return veo.list_models(include_remote=include_remote)


@app.tool()
def generate_start(
    prompt: str,
    model: Optional[str] = None,
    input_image_path: Optional[str] = None,
    input_video_path: Optional[str] = None,
    extract_at: Optional[float] = None,
    options: Optional[Dict] = None,
) -> dict:
    """Start a video generation job.

    - prompt: required text prompt
    - model: e.g., "veo-3.0-fast-generate-preview"; if omitted, SDK default is used
    - input_image_path: path to seed image for image→video
    - input_video_path: path to source video for continuation
    - extract_at: seconds offset for continuation (use -1.0 for last second)
    - options: pass-through config, e.g. {aspect_ratio: "16:9", negative_prompt: "...",
      person_generation: "allow_all"}
    Returns {job_id, status, progress, message, kind, created_at}.
    """
    params: Dict = {"prompt": prompt}
    if model:
        params["model"] = model
    if input_image_path:
        params["input_image_path"] = input_image_path
    if input_video_path:
        params["input_video_path"] = input_video_path
    if extract_at is not None:
        params["extract_at"] = extract_at
    if options:
        params["options"] = options
    return veo.generate_start(params)


@app.tool()
async def generate_get(job_id: str, ctx: Context, wait_ms: int | None = None) -> dict:
    """Get job status; optionally stream progress.

    - job_id: identifier from generate_start
    - wait_ms: if provided, stream progress events and return when terminal or
      time window elapses. Use 0/None for immediate snapshot.
    Returns latest job status; includes result when complete.
    """
    if not wait_ms or wait_ms <= 0:
        return veo.generate_get(job_id)
    import time

    deadline = time.time() + (wait_ms / 1000.0)
    last_progress = -1
    while time.time() < deadline:
        status = veo.generate_get(job_id)
        progress = int(status.get("progress", 0))
        if progress != last_progress:
            last_progress = progress
            try:
                await ctx.report_progress(progress=progress / 100.0, total=1.0, message=status.get("message", ""))
            except Exception:
                pass
        if status.get("status") in {"complete", "failed", "cancelled"}:
            return status
        await ctx.sleep(0.5)
    return veo.generate_get(job_id)


@app.tool()
def generate_cancel(job_id: str) -> dict:
    """Request cooperative cancellation for a running job."""
    return veo.generate_cancel(job_id)


@app.resource("videos://recent/{limit}")
def list_recent_videos(limit: int = 10) -> list[dict]:
    """List recent generated videos with URLs and metadata.

    - limit: max items (default 10).
    Returns array of {path, url, metadata, modified}.
    """
    storage = veo.StorageManager()
    files = sorted(storage.videos_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)[: max(0, int(limit))]
    out: list[dict] = []
    for p in files:
        try:
            info = get_video_info(p)
        except Exception:
            info = {}
        out.append({
            "path": str(p),
            "url": storage.get_url(p),
            "metadata": info,
            "modified": p.stat().st_mtime,
        })
    return out


@app.resource("job://{job_id}")
def get_job(job_id: str) -> dict:
    """Retrieve the persisted job record by id."""
    store = JobStore()
    record = store.read(job_id)
    if not record:
        return {"error_code": "VALIDATION", "error_message": f"job_id not found: {job_id}"}
    return {
        "job_id": record.job_id,
        "status": record.status,
        "progress": record.progress,
        "message": record.message,
        "kind": record.kind,
        "result": record.result,
        "error_code": record.error_code,
        "error_message": record.error_message,
        "remote_operation_id": record.remote_operation_id,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "cancel_requested": record.cancel_requested,
    }


@app.tool()
async def continue_video(
    video_path: str,
    prompt: str,
    ctx: Context,
    model: Optional[str] = None,
    extract_at: float = -1.0,
    overlap: float = 1.0,
    wait_ms: int = 900_000,
    aspect_ratio: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    person_generation: Optional[str] = None,
) -> dict:
    """Generate a continuation and stitch with the source clip.

    Parameters:
      - video_path: source clip to continue
      - prompt: continuation prompt
      - model: Veo model id (optional)
      - extract_at: seconds offset for frame extraction (default -1.0 = last second)
      - overlap: seconds to trim from end of source before concatenation (default 1.0)
      - wait_ms: max time to stream progress before returning snapshot (default 15 min)
      - aspect_ratio: requested AR (e.g., "16:9"; Veo 2 also supports "9:16")
      - negative_prompt: text to avoid
      - person_generation: policy value (allow_all|allow_adult|dont_allow)
    Returns {stage, generated?, stitched?}.
    """
    params: Dict = {"prompt": prompt, "input_video_path": video_path, "extract_at": extract_at}
    if model:
        params["model"] = model
    # pass optional config
    options: Dict = {}
    if aspect_ratio:
        options["aspect_ratio"] = aspect_ratio
    if negative_prompt:
        options["negative_prompt"] = negative_prompt
    if person_generation:
        options["person_generation"] = person_generation
    if options:
        params["options"] = options

    start = veo.generate_start(params)
    job_id = start["job_id"]

    # stream progress
    import time
    deadline = time.time() + (wait_ms / 1000.0)
    last_progress = -1
    while time.time() < deadline:
        status = veo.generate_get(job_id)
        prog = int(status.get("progress", 0))
        if prog != last_progress:
            last_progress = prog
            try:
                await ctx.report_progress(progress=prog / 100.0, total=1.0, message=status.get("message", "Generating"))
            except Exception:
                pass
        if status.get("status") in {"complete", "failed", "cancelled"}:
            gen_result = status
            break
        await ctx.sleep(0.5)
    else:
        return {"stage": "generation", **veo.generate_get(job_id)}

    if gen_result.get("status") != "complete" or not gen_result.get("result"):
        return {"stage": "generation", **gen_result}

    new_clip_path = gen_result["result"].get("path")
    if not new_clip_path:
        return {"stage": "generation", "error_code": "UNKNOWN", "error_message": "Missing result path"}

    try:
        stitched = veo.stitch_videos([Path(video_path), Path(new_clip_path)], overlap=overlap)
    except Exception as e:
        return {"stage": "stitch", "error_code": "STITCH", "error_message": str(e)}

    return {"stage": "complete", "generated": gen_result["result"], "stitched": stitched.to_dict()}


def main() -> None:
    app.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()


