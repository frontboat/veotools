#!/usr/bin/env python3
# Minimal MCP server for veo-tools

from pathlib import Path
from typing import Optional, List, Dict
import time
from mcp.server.fastmcp import FastMCP, Context
import veotools as veo
from veotools.mcp_api import JobStore
from veotools.process.extractor import get_video_info

app = FastMCP("veo-tools")

@app.tool()
def preflight() -> dict:
    return veo.preflight()

@app.tool()
def version() -> dict:
    return veo.version()

@app.tool()
def list_models(include_remote: bool = True) -> dict:
    """List available models for generation with capability flags."""
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
    params: Dict = {"prompt": prompt}
    if model: params["model"] = model
    if input_image_path: params["input_image_path"] = input_image_path
    if input_video_path: params["input_video_path"] = input_video_path
    if extract_at is not None: params["extract_at"] = extract_at
    if options: params["options"] = options
    return veo.generate_start(params)

@app.tool()
async def generate_get(job_id: str, ctx: Context, wait_ms: int | None = None) -> dict:
    """Get job status; optionally stream progress for up to wait_ms milliseconds."""
    # If no wait requested, return immediate status
    if not wait_ms or wait_ms <= 0:
        return veo.generate_get(job_id)

    deadline = time.time() + (wait_ms / 1000.0)
    last_progress = -1
    while time.time() < deadline:
        status = veo.generate_get(job_id)
        # Report progress if changed
        progress = int(status.get("progress", 0))
        if progress != last_progress:
            last_progress = progress
            try:
                await ctx.report_progress(progress=progress / 100.0, total=1.0, message=status.get("message", ""))
            except Exception:
                pass
        # If job terminal, return immediately
        if status.get("status") in {"complete", "failed", "cancelled"}:
            return status
        await ctx.sleep(0.5)
    # Timeboxed: return latest snapshot
    return veo.generate_get(job_id)


# Resources
@app.resource("job://{job_id}")
def get_job(job_id: str) -> dict:
    """Retrieve raw job record JSON for a given job_id."""
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


@app.resource("videos://recent/{limit}")
def list_recent_videos(limit: int = 10) -> list[dict]:
    """List recent generated videos with URLs and basic metadata."""
    storage = veo.StorageManager()
    videos_dir = storage.videos_dir
    files = sorted(videos_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)[: max(0, int(limit))]
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


# High-level convenience: continue a video and stitch seamlessly
@app.tool()
async def continue_video(
    video_path: str,
    prompt: str,
    ctx: Context,
    model: Optional[str] = None,
    extract_at: float = -1.0,
    overlap: float = 1.0,
    wait_ms: int = 900_000,
) -> dict:
    """Generate a continuation from the end of `video_path` and stitch it.

    - Extracts a frame at `extract_at` seconds relative to the end (default -1.0)
    - Generates an ~8s continuation (model-dependent)
    - Stitches the original with the new clip trimming `overlap` seconds from the first
    - Streams progress during generation and stitching
    """
    # Submit generation
    params: Dict[str, Dict] = {
        "prompt": prompt,
        "input_video_path": video_path,
        "extract_at": extract_at,
    }
    if model:
        params["model"] = model
    start = veo.generate_start(params)
    job_id = start["job_id"]

    # Stream generation progress up to wait_ms
    await ctx.info(f"Generating continuation for {Path(video_path).name}")
    deadline = time.time() + (wait_ms / 1000.0)
    gen_result: Optional[dict] = None
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

    if not gen_result:
        # Timeboxed, return current status
        return {"stage": "generation", **veo.generate_get(job_id)}

    if gen_result.get("status") != "complete" or not gen_result.get("result"):
        return {"stage": "generation", **gen_result}

    new_clip_path = gen_result["result"].get("path")
    if not new_clip_path:
        return {"stage": "generation", "error_code": "UNKNOWN", "error_message": "Missing result path"}

    # Stitch originals
    await ctx.info("Stitching original with continuation")
    try:
        stitched = veo.stitch_videos([Path(video_path), Path(new_clip_path)], overlap=overlap)
    except Exception as e:
        return {"stage": "stitch", "error_code": "STITCH", "error_message": str(e)}

    return {
        "stage": "complete",
        "generated": gen_result["result"],
        "stitched": stitched.to_dict(),
    }

@app.tool()
def generate_cancel(job_id: str) -> dict:
    return veo.generate_cancel(job_id)

@app.tool()
def extract_frame(video_path: str, time_offset: float = -1.0) -> dict:
    frame = veo.extract_frame(Path(video_path), time_offset)
    url = veo.StorageManager().get_url(Path(frame))
    info = veo.get_video_info(Path(video_path))
    return {"path": str(frame), "url": url, "metadata": info}

@app.tool()
def stitch_videos(video_paths: List[str], overlap: float = 1.0) -> dict:
    result = veo.stitch_videos([Path(p) for p in video_paths], overlap=overlap)
    return result.to_dict()

if __name__ == "__main__":
    # Run over stdio transport for MCP clients like Cursor
    app.run(transport="stdio")