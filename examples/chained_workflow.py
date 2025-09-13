#!/usr/bin/env python3
"""Create multi-scene videos using the Bridge workflow API.

The Bridge API provides a fluent interface for chaining video operations:
- Generate multiple scenes from text/images/videos
- Stitch scenes together with smooth transitions
- Track progress across the entire workflow
- Save and resume workflows

Usage:
    python examples/chained_workflow.py
    python examples/chained_workflow.py --interactive
    python examples/chained_workflow.py --model veo-2.0-generate-001
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import json
import veotools as veo


def progress_bar(message: str, percent: int):
    """Display a nice progress bar."""
    bar_length = 40
    filled = int(bar_length * percent / 100)
    bar = '█' * filled + '░' * (bar_length - filled)
    print(f"\r  [{bar}] {percent:3}% - {message}", end='', flush=True)
    if percent >= 100:
        print()  # New line when complete


def simple_story_demo(model: str = None):
    """Create a simple 3-scene story."""
    print("\n" + "="*60)
    print("Simple Story Demo")
    print("="*60)
    
    if not model:
        models = veo.list_models(include_remote=True)["models"]
        veo_models = [m for m in models if m["id"].startswith("veo-")]
        model = next((m["id"] for m in veo_models if "fast" in m["id"]), 
                     "veo-3.0-fast-generate-preview")
    
    print(f"\nGenerating 3-scene story with {model}...")
    
    bridge = veo.Bridge("nature_story")
    
    # Chain operations fluently
    result = (bridge
        .with_progress(progress_bar)
        .generate("Sunrise over misty mountains, golden light breaking through clouds", model=model)
        .generate("Eagle soaring through the mountain peaks, majestic flight", model=model)
        .generate("The eagle lands on a cliff edge as sun sets behind mountains", model=model)
        .stitch(overlap=1.0)
        .save()
    )
    
    print(f"\n✓ Story complete: {result}")
    
    # Show workflow summary
    workflow = bridge.to_dict()
    print(f"\nWorkflow Summary:")
    print(f"  Total scenes: {len([s for s in workflow['steps'] if s['action'] == 'generate'])}")
    print(f"  Output: {result}")
    
    return result


def mixed_media_demo(model: str = None):
    """Demonstrate mixing existing media with AI generation."""
    print("\n" + "="*60)
    print("Mixed Media Demo")
    print("="*60)
    
    if not model:
        models = veo.list_models(include_remote=True)["models"]
        veo_models = [m for m in models if m["id"].startswith("veo-")]
        model = next((m["id"] for m in veo_models if "fast" in m["id"]), 
                     "veo-3.0-fast-generate-preview")
    
    # Check for existing media files
    videos = list(Path("output/videos").glob("*.mp4"))
    images = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        images.extend(Path(".").glob(ext))
    
    if not videos and not images:
        print("No existing media found. Generating sample content first...")
        
        # Generate a video to use
        sample = veo.generate_from_text(
            "A peaceful garden with flowers swaying in the breeze",
            model=model,
            on_progress=progress_bar
        )
        videos = [sample.path]
    
    print(f"\nCreating mixed media sequence...")
    
    bridge = veo.Bridge("mixed_media")
    bridge.with_progress(progress_bar)
    
    if videos:
        print(f"  Adding video: {videos[0].name}")
        bridge.add_media(videos[0])
        bridge.generate("Transform into a magical fantasy garden with glowing particles", model=model)
    
    if images:
        print(f"  Adding image: {images[0].name}")
        bridge.add_media(images[0])
        bridge.generate("Bring the image to life with gentle movement", model=model)
    
    # Add text-only generation
    bridge.generate("Fade to a starry night sky with shooting stars", model=model)
    
    # Stitch everything together
    result = bridge.stitch(overlap=0.5).save()
    
    print(f"\n✓ Mixed media complete: {result}")
    
    return result


def interactive_workflow(model: str = None):
    """Build a workflow interactively."""
    print("\n" + "="*60)
    print("Interactive Workflow Builder")
    print("="*60)
    
    if not model:
        models = veo.list_models(include_remote=True)["models"]
        veo_models = [m for m in models if m["id"].startswith("veo-")]
        model = next((m["id"] for m in veo_models if "fast" in m["id"]), 
                     "veo-3.0-fast-generate-preview")
    
    bridge = veo.Bridge("interactive")
    bridge.with_progress(progress_bar)
    
    print(f"\nUsing model: {model}")
    print("\nBuild your video by adding scenes. Commands:")
    print("  text <prompt>  - Generate from text")
    print("  video <path>   - Add existing video")
    print("  image <path>   - Add existing image")
    print("  done           - Finish and stitch")
    print("  quit           - Exit without saving")
    
    scenes = []
    
    while True:
        print(f"\nScene {len(scenes) + 1}")
        command = input("> ").strip()
        
        if command == "quit":
            print("Exiting...")
            return None
        
        if command == "done":
            if len(scenes) < 2:
                print("Need at least 2 scenes to stitch. Add more or quit.")
                continue
            break
        
        parts = command.split(None, 1)
        if len(parts) < 2:
            print("Invalid command. Try: text <prompt>, video <path>, image <path>")
            continue
        
        cmd, arg = parts
        
        try:
            if cmd == "text":
                bridge.generate(arg, model=model)
                scenes.append(f"Text: {arg[:50]}...")
                print(f"✓ Added text generation")
                
            elif cmd == "video":
                path = Path(arg)
                if not path.exists():
                    print(f"File not found: {path}")
                    continue
                bridge.add_media(path)
                scenes.append(f"Video: {path.name}")
                print(f"✓ Added video")
                
            elif cmd == "image":
                path = Path(arg)
                if not path.exists():
                    print(f"File not found: {path}")
                    continue
                bridge.add_media(path)
                prompt = input("  Prompt for image animation: ").strip()
                bridge.generate(prompt or "bring the image to life", model=model)
                scenes.append(f"Image: {path.name}")
                print(f"✓ Added image with animation")
                
            else:
                print(f"Unknown command: {cmd}")
                
        except Exception as e:
            print(f"Error: {e}")
    
    print("\nStitching scenes together...")
    overlap = float(input("Overlap duration in seconds (default 1.0): ").strip() or "1.0")
    
    result = bridge.stitch(overlap=overlap).save()
    
    print(f"\n✓ Workflow complete: {result}")
    print(f"\nScenes included:")
    for i, scene in enumerate(scenes, 1):
        print(f"  {i}. {scene}")
    
    # Save workflow
    workflow_path = Path("output/workflow_interactive.json")
    with open(workflow_path, "w") as f:
        json.dump(bridge.to_dict(), f, indent=2)
    print(f"\nWorkflow saved: {workflow_path}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Create multi-scene videos with Bridge API")
    parser.add_argument("--demo", choices=["story", "mixed", "all"], default="story",
                        help="Which demo to run (default: story)")
    parser.add_argument("--interactive", action="store_true",
                        help="Build workflow interactively")
    parser.add_argument("--model", help="Model to use for generation")
    
    args = parser.parse_args()
    
    veo.init()
    
    if args.interactive:
        interactive_workflow(args.model)
    elif args.demo == "all":
        simple_story_demo(args.model)
        mixed_media_demo(args.model)
    elif args.demo == "mixed":
        mixed_media_demo(args.model)
    else:  # story
        simple_story_demo(args.model)
    
    print("\n" + "="*60)
    print("Workflow examples complete!")
    print("="*60)


if __name__ == "__main__":
    main()