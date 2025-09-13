#!/usr/bin/env python3
"""Generate video from text prompt using Google Veo.

Simple example showing text-to-video generation with progress tracking.

Usage:
    python examples/text_to_video.py "Your prompt here"
    python examples/text_to_video.py "Your prompt" --model veo-2.0-generate-001
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import veotools as veo


def main():
    parser = argparse.ArgumentParser(description="Generate video from text prompt")
    parser.add_argument("prompt", help="Text prompt for video generation")
    parser.add_argument("--model", help="Model to use (default: auto-select fast model)")
    parser.add_argument("--duration", type=int, help="Duration in seconds (Veo 2.0 only)")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    
    args = parser.parse_args()
    
    veo.init()
    
    # Auto-select fast model if not specified
    if not args.model:
        models = veo.list_models(include_remote=True)["models"]
        veo_models = [m for m in models if m["id"].startswith("veo-")]
        args.model = next((m["id"] for m in veo_models if "fast" in m["id"]), 
                          "veo-3.0-fast-generate-preview")
    
    if not args.quiet:
        print(f"Generating video...")
        print(f"  Prompt: {args.prompt}")
        print(f"  Model: {args.model}")
        if args.duration and "veo-2.0" in args.model:
            print(f"  Duration: {args.duration}s")
    
    # Set up generation parameters
    kwargs = {"model": args.model}
    if args.duration and "veo-2.0" in args.model:
        kwargs["duration_seconds"] = args.duration
    
    # Add progress callback unless quiet mode
    if not args.quiet:
        kwargs["on_progress"] = lambda msg, pct: print(f"  {msg}: {pct}%")
    
    # Generate video
    result = veo.generate_from_text(args.prompt, **kwargs)
    
    print(f"\n✓ Video saved: {result.path}")
    print(f"  Duration: {result.metadata.duration:.1f}s")
    print(f"  Resolution: {result.metadata.width}x{result.metadata.height}")
    print(f"  FPS: {result.metadata.fps}")


if __name__ == "__main__":
    main()