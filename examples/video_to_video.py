#!/usr/bin/env python3
"""Continue or transform existing videos with Google Veo.

This example shows how to:
1. Continue a video from its last frame
2. Optionally stitch the original and continuation together

Usage:
    python examples/video_to_video.py input.mp4 "what happens next"
    python examples/video_to_video.py input.mp4 "zoom out to reveal" --stitch
    python examples/video_to_video.py input.mp4 "continue the scene" --frame-time 5.0
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import veotools as veo


def main():
    parser = argparse.ArgumentParser(description="Continue or transform existing videos")
    parser.add_argument("video", help="Input video file path")
    parser.add_argument("prompt", help="Continuation/transformation prompt")
    parser.add_argument("--model", help="Model to use (default: auto-select fast model)")
    parser.add_argument("--frame-time", type=float, default=-1.0,
                        help="Time to extract frame at (negative = from end, default: -1.0)")
    parser.add_argument("--stitch", action="store_true", 
                        help="Stitch original and continuation together")
    parser.add_argument("--overlap", type=float, default=1.0,
                        help="Overlap duration for stitching in seconds (default: 1.0)")
    parser.add_argument("--duration", type=int, help="Duration in seconds (Veo 2.0 only)")
    
    args = parser.parse_args()
    
    veo.init()
    
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)
    
    # Auto-select fast model if not specified
    if not args.model:
        models = veo.list_models(include_remote=True)["models"]
        veo_models = [m for m in models if m["id"].startswith("veo-")]
        args.model = next((m["id"] for m in veo_models if "fast" in m["id"]), 
                          "veo-3.0-fast-generate-preview")
    
    # Get video info
    info = veo.get_video_info(video_path)
    
    print(f"Source video:")
    print(f"  File: {video_path.name}")
    print(f"  Duration: {info['duration']:.1f}s")
    print(f"  Resolution: {info['width']}x{info['height']}")
    print()
    print(f"Generating continuation...")
    print(f"  Prompt: {args.prompt}")
    print(f"  Model: {args.model}")
    print(f"  Extract frame at: {args.frame_time}s")
    
    # Set up generation parameters
    kwargs = {
        "model": args.model,
        "extract_at": args.frame_time,
        "on_progress": lambda msg, pct: print(f"  {msg}: {pct}%")
    }
    
    if args.duration and "veo-2.0" in args.model:
        kwargs["duration_seconds"] = args.duration
        print(f"  Duration: {args.duration}s")
    
    # Generate continuation
    result = veo.generate_from_video(video_path, args.prompt, **kwargs)
    
    print(f"\n✓ Continuation saved: {result.path}")
    print(f"  Duration: {result.metadata.duration:.1f}s")
    
    # Optionally stitch videos together
    if args.stitch:
        print(f"\nStitching videos with {args.overlap}s overlap...")
        
        stitched = veo.stitch_videos(
            [video_path, result.path],
            overlap=args.overlap,
            on_progress=lambda msg, pct: print(f"  {msg}: {pct}%")
        )
        
        print(f"\n✓ Stitched video saved: {stitched.path}")
        print(f"  Total duration: {stitched.metadata.duration:.1f}s")
        print(f"  Resolution: {stitched.metadata.width}x{stitched.metadata.height}")


if __name__ == "__main__":
    main()