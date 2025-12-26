"""Veo Tools - A toolkit for AI-powered video generation and stitching."""

import logging

logger = logging.getLogger(__name__)

from .core import VeoClient, StorageManager, ProgressTracker, ModelConfig
from .models import VideoResult, VideoMetadata, Workflow, JobStatus

from .generate.video import (
    generate_from_text,
    generate_from_image,
    generate_from_video,
    extend_video,
    generate_with_reference_images,
    generate_with_interpolation,
)

from .process.extractor import (
    extract_frame,
    extract_frames,
    get_video_info
)

from .stitch.seamless import (
    stitch_videos,
    stitch_with_transitions,
    create_transition_points
)

from .api.bridge import Bridge
from .api.mcp_api import (
    preflight,
    version,
    list_models,
    generate_start,
    generate_get,
    generate_cancel,
    cache_create_from_files,
    cache_get,
    cache_list,
    cache_update,
    cache_delete,
    plan_scenes,
)
from .plan import (
    ScenePlan,
    CharacterProfile,
    Clip,
    SceneWriter,
    generate_scene_plan,
    PlanExecutionResult,
    execute_scene_plan,
)

__version__ = "0.2.0"

__all__ = [
    "VeoClient",
    "StorageManager",
    "ProgressTracker",
    "ModelConfig",
    "VideoResult",
    "VideoMetadata",
    "Workflow",
    "JobStatus",
    # Generation functions
    "generate_from_text",
    "generate_from_image",
    "generate_from_video",
    # Veo 3.1 features
    "extend_video",
    "generate_with_reference_images",
    "generate_with_interpolation",
    # Processing
    "extract_frame",
    "extract_frames",
    "get_video_info",
    "stitch_videos",
    "stitch_with_transitions",
    "create_transition_points",
    "Bridge",
    "ScenePlan",
    "CharacterProfile",
    "Clip",
    "SceneWriter",
    "generate_scene_plan",
    "PlanExecutionResult",
    "execute_scene_plan",
    # MCP-friendly APIs
    "preflight",
    "version",
    "generate_start",
    "generate_get",
    "generate_cancel",
    "list_models",
    "cache_create_from_files",
    "cache_get",
    "cache_list",
    "cache_update",
    "cache_delete",
    "plan_scenes",
]

def init(api_key: str = None, log_level: str = "WARNING"):
    import os
    if api_key:
        provider = (os.getenv("VEO_PROVIDER", "google") or "google").strip().lower()
        if provider == "daydreams":
            os.environ["DAYDREAMS_API_KEY"] = api_key
        else:
            os.environ["GEMINI_API_KEY"] = api_key
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(name)s - %(levelname)s - %(message)s'
    )
    
    VeoClient()
    
    logger.info(f"veotools {__version__} initialized")
