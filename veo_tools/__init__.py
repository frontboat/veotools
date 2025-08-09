"""Veo Tools - A toolkit for AI-powered video generation and stitching."""

import logging

logger = logging.getLogger(__name__)

from .core import VeoClient, StorageManager, ProgressTracker, ModelConfig
from .models import VideoResult, VideoMetadata, Workflow, JobStatus

from .generate.video import (
    generate_from_text,
    generate_from_image,
    generate_from_video
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

from .bridge import Bridge
from .mcp_api import (
    preflight,
    version,
    list_models,
    generate_start,
    generate_get,
    generate_cancel,
)

__version__ = "0.1.0"

__all__ = [
    "VeoClient",
    "StorageManager", 
    "ProgressTracker",
    "ModelConfig",
    "VideoResult",
    "VideoMetadata",
    "Workflow",
    "JobStatus",
    "generate_from_text",
    "generate_from_image",
    "generate_from_video",
    "extract_frame",
    "extract_frames",
    "get_video_info",
    "stitch_videos",
    "stitch_with_transitions",
    "create_transition_points",
    "Bridge",
    # MCP-friendly APIs
    "preflight",
    "version",
    "generate_start",
    "generate_get",
    "generate_cancel",
    "list_models",
]

def init(api_key: str = None, log_level: str = "WARNING"):
    import os
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(name)s - %(levelname)s - %(message)s'
    )
    
    VeoClient()
    
    logger.info(f"veotools {__version__} initialized")