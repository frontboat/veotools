#!/usr/bin/env python3
"""
Example: Video-to-Video Continuation

Takes an existing video and generates an AI continuation from its last frame.
Perfect for extending videos from your phone or creating seamless sequences.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import veotools as veo


def continue_my_video(video_path: str, continuation_prompt: str, model: str | None = None):
    """Continue a video with AI generation.
    
    Args:
        video_path: Path to your video file
        continuation_prompt: What should happen next in the video
        model: Optional model to use (will prompt if not provided)
    """
    veo.init()
    
    video_path = Path(video_path)
    
    if not video_path.exists():
        print(f"Error: Video not found at {video_path}")
        return
    
    if not model:
        models = veo.list_models(include_remote=True)["models"]
        veo_models = [m for m in models if m["id"].startswith("veo-")]
        model = next((m["id"] for m in veo_models if "fast" in m["id"]), "veo-3.0-fast-generate-preview")
    
    print(f"\nContinuing: {video_path.name}")
    print(f"Prompt: {continuation_prompt}")
    print(f"Model: {model}")
    
    kwargs = {}
    if "veo-2.0" in model:
        kwargs["duration_seconds"] = 5
        print(f"   Duration: 5 seconds")
    else:
        print(f"   Duration: ~8 seconds (model default)")
        print(f"   Audio: Enabled")
    
    print("-" * 50)
    
    result = veo.generate_from_video(
        video_path,
        continuation_prompt,
        extract_at=-1.0,
        model=model,
        on_progress=lambda msg, pct: print(f"  {msg}: {pct}%"),
        **kwargs
    )
    
    print(f"\nGenerated: {result.path}")
    
    print("\nStitching...")
    
    stitched = veo.stitch_videos(
        [video_path, result.path],
        overlap=1.0,
        on_progress=lambda msg, pct: print(f"  {msg}: {pct}%")
    )
    
    print(f"\nFinal: {stitched.path}")
    print(f"   Duration: {stitched.metadata.duration:.1f} seconds")
    
    return stitched.path


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python examples/video_to_video.py <video_file> <prompt> [model]")
        print("\nExamples:")
        print("  python continue_video.py dog.mp4 'the dog finds a treasure chest'")
        print("  python continue_video.py dog.mp4 'the dog finds gold' veo-2.0-generate-001")
        print("\nAvailable models:")
        print("  - veo-3.0-fast-generate-preview (default)")
        print("  - veo-3.0-generate-preview")
        print("  - veo-2.0-generate-001")
        sys.exit(1)
    
    video_file = sys.argv[1]
    prompt = sys.argv[2]
    model = sys.argv[3] if len(sys.argv) > 3 else None
    
    continue_my_video(video_file, prompt, model)