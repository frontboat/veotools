#!/usr/bin/env python3
"""
Example: All Veo Tools Functions

This example demonstrates every function in the Veo Tools SDK.
Run each example individually to see how each function works.
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

import veo_tools as veo


def demo_generate_from_text():
    """Demo: Generate video from text prompt."""
    print("\n" + "="*60)
    print("DEMO: generate_from_text")
    print("="*60)
    
    print("\nSelect Veo model:")
    print("1. veo-3.0-fast-generate-preview (Lower quota usage, 8s videos)")
    print("2. veo-3.0-generate-preview (Medium quota usage, 8s videos)")
    print("3. veo-2.0-generate-001 (Higher quota usage, 5s videos, more control)")
    
    choice = input("\nSelect model (1-3, default=1): ").strip() or "1"
    models = {
        "1": "veo-3.0-fast-generate-preview",
        "2": "veo-3.0-generate-preview",
        "3": "veo-2.0-generate-001"
    }
    model = models.get(choice, "veo-3.0-fast-generate-preview")
    
    print(f"\nUsing model: {model}")
    
    result = veo.generate_from_text(
        prompt="A butterfly landing on a flower in slow motion",
        model=model,
        on_progress=lambda msg, pct: print(f"  {msg}: {pct}%")
    )
    
    print(f"Generated: {result.path}")
    print(f"   Status: {result.status.value}")
    print(f"   Model: {result.model}")
    return result


def demo_generate_from_image():
    """Demo: Generate video from an image."""
    print("\n" + "="*60)
    print("DEMO: generate_from_image")
    print("="*60)
    
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        image_files.extend(Path(".").glob(ext))
    
    if image_files:
        image_path = image_files[0]
        print(f"Using image: {image_path}")
    else:
        videos = list(Path("output/videos").glob("*.mp4"))
        if not videos:
            print("No images found in project directory and no videos to extract from.")
            print("   Please add an image file or run generate_from_text demo first.")
            return None
        
        print("No images found, extracting frame from existing video...")
        image_path = veo.extract_frame(videos[0], time_offset=1.0)
        print(f"Using extracted frame: {image_path}")
    
    print("\nSelect Veo model:")
    print("1. veo-3.0-fast-generate-preview (Lower quota usage, 8s videos)")
    print("2. veo-3.0-generate-preview (Medium quota usage, 8s videos)")
    print("3. veo-2.0-generate-001 (Higher quota usage, 5s videos, more control)")
    
    choice = input("\nSelect model (1-3, default=1): ").strip() or "1"
    models = {
        "1": "veo-3.0-fast-generate-preview",
        "2": "veo-3.0-generate-preview",
        "3": "veo-2.0-generate-001"
    }
    model = models.get(choice, "veo-3.0-fast-generate-preview")
    
    print(f"\nUsing model: {model}")
    
    result = veo.generate_from_image(
        image_path=image_path,
        prompt="the scene comes to life with magical particles",
        model=model,
        on_progress=lambda msg, pct: print(f"  {msg}: {pct}%")
    )
    
    print(f"Generated: {result.path}")
    return result


def demo_generate_from_video():
    """Demo: Continue a video from its last frame."""
    print("\n" + "="*60)
    print("DEMO: generate_from_video")
    print("="*60)
    
    videos = list(Path("output/videos").glob("*.mp4"))
    if not videos:
        print("No videos found. Generate one first with generate_from_text.")
        return None
    
    source_video = videos[0]
    print(f"Continuing from: {source_video.name}")
    
    print("\nSelect Veo model:")
    print("1. veo-3.0-fast-generate-preview (Lower quota usage, 8s videos)")
    print("2. veo-3.0-generate-preview (Medium quota usage, 8s videos)")
    print("3. veo-2.0-generate-001 (Higher quota usage, 5s videos, more control)")
    
    choice = input("\nSelect model (1-3, default=1): ").strip() or "1"
    models = {
        "1": "veo-3.0-fast-generate-preview",
        "2": "veo-3.0-generate-preview",
        "3": "veo-2.0-generate-001"
    }
    model = models.get(choice, "veo-3.0-fast-generate-preview")
    
    print(f"\nUsing model: {model}")
    
    result = veo.generate_from_video(
        video_path=source_video,
        prompt="the camera zooms out revealing a larger scene",
        extract_at=-1.0,
        model=model,
        on_progress=lambda msg, pct: print(f"  {msg}: {pct}%")
    )
    
    print(f"Generated continuation: {result.path}")
    return result


def demo_extract_frame():
    """Demo: Extract a single frame from video."""
    print("\n" + "="*60)
    print("DEMO: extract_frame")
    print("="*60)
    
    videos = list(Path("output/videos").glob("*.mp4"))
    if not videos:
        print("No videos found. Generate one first.")
        return None
    
    video = videos[0]
    print(f"Extracting from: {video.name}")
    
    frame_start = veo.extract_frame(video, time_offset=1.0)
    print(f"Frame at 1.0s: {frame_start}")
    
    frame_end = veo.extract_frame(video, time_offset=-1.0)
    print(f"Frame at -1.0s: {frame_end}")
    
    return frame_start, frame_end


def demo_extract_frames():
    """Demo: Extract multiple frames from video."""
    print("\n" + "="*60)
    print("DEMO: extract_frames")
    print("="*60)
    
    videos = list(Path("output/videos").glob("*.mp4"))
    if not videos:
        print("No videos found. Generate one first.")
        return None
    
    video = videos[0]
    print(f"Extracting from: {video.name}")
    
    times = [0.0, 1.0, 2.0, -2.0, -1.0]
    frames = veo.extract_frames(video, times)
    
    print(f"Extracted {len(frames)} frames:")
    for i, frame in enumerate(frames):
        print(f"   Frame {i+1}: {frame.name}")
    
    return frames


def demo_get_video_info():
    """Demo: Get information about a video."""
    print("\n" + "="*60)
    print("DEMO: get_video_info")
    print("="*60)
    
    videos = list(Path("output/videos").glob("*.mp4"))
    if not videos:
        print("No videos found. Generate one first.")
        return None
    
    video = videos[0]
    print(f"Analyzing: {video.name}")
    
    info = veo.get_video_info(video)
    
    print("Video Information:")
    print(f"   Resolution: {info['width']}x{info['height']}")
    print(f"   FPS: {info['fps']}")
    print(f"   Duration: {info['duration']:.2f} seconds")
    print(f"   Frame Count: {info['frame_count']}")
    
    return info


def demo_stitch_videos():
    """Demo: Stitch multiple videos together."""
    print("\n" + "="*60)
    print("DEMO: stitch_videos")
    print("="*60)
    
    videos = list(Path("output/videos").glob("*.mp4"))
    if len(videos) < 2:
        print("Need at least 2 videos. Generate more first.")
        return None
    
    video_paths = videos[:2]
    print(f"Stitching {len(video_paths)} videos:")
    for v in video_paths:
        print(f"   - {v.name}")
    
    result = veo.stitch_videos(
        video_paths=video_paths,
        overlap=1.0,
        on_progress=lambda msg, pct: print(f"  {msg}: {pct}%")
    )
    
    print(f"Stitched video: {result.path}")
    print(f"   Duration: {result.metadata.duration:.1f} seconds")
    return result


def demo_create_transition_points():
    """Demo: Extract frames for creating transitions."""
    print("\n" + "="*60)
    print("DEMO: create_transition_points")
    print("="*60)
    
    videos = list(Path("output/videos").glob("*.mp4"))
    if len(videos) < 2:
        print("Need at least 2 videos.")
        return None
    
    video_a = videos[0]
    video_b = videos[1]
    print(f"Video A: {video_a.name}")
    print(f"Video B: {video_b.name}")
    
    frame_a, frame_b = veo.create_transition_points(
        video_a,
        video_b,
        extract_points={"a_end": -1.0, "b_start": 1.0}
    )
    
    print(f"Frame A (end): {frame_a}")
    print(f"Frame B (start): {frame_b}")
    print("   These frames can be used to generate AI transitions")
    
    return frame_a, frame_b


def demo_bridge_basic():
    """Demo: Basic Bridge workflow."""
    print("\n" + "="*60)
    print("DEMO: Bridge - Basic Workflow")
    print("="*60)
    
    print("\nSelect Veo model for generation:")
    print("1. veo-3.0-fast-generate-preview (Lower quota usage, 8s videos)")
    print("2. veo-3.0-generate-preview (Medium quota usage, 8s videos)")
    print("3. veo-2.0-generate-001 (Higher quota usage, 5s videos, more control)")
    
    choice = input("\nSelect model (1-3, default=1): ").strip() or "1"
    models = {
        "1": "veo-3.0-fast-generate-preview",
        "2": "veo-3.0-generate-preview",
        "3": "veo-2.0-generate-001"
    }
    model = models.get(choice, "veo-3.0-fast-generate-preview")
    
    print(f"\nUsing model: {model}")
    
    bridge = veo.Bridge("demo_workflow")
    
    result = (bridge
        .with_progress(lambda msg, pct: print(f"  {msg}: {pct}%"))
        .generate("A seed growing into a tree time-lapse", model=model)
        .generate("The tree blooming with flowers", model=model)
        .stitch(overlap=1.0)
        .save()
    )
    
    print(f"Workflow complete: {result}")
    
    workflow_data = bridge.to_dict()
    print(f"\nWorkflow Summary:")
    print(f"   ID: {workflow_data['id']}")
    print(f"   Steps: {len(workflow_data['steps'])}")
    
    return bridge


def demo_videoResult_serialization():
    """Demo: VideoResult JSON serialization."""
    print("\n" + "="*60)
    print("DEMO: VideoResult Serialization")
    print("="*60)
    
    result = veo.VideoResult()
    result.prompt = "Test prompt"
    result.model = "veo-3.0-fast-generate-preview"
    result.update_progress("Processing", 50)
    
    data = result.to_dict()
    
    print("VideoResult as JSON:")
    print(json.dumps(data, indent=2))
    
    print("\nThis data structure is ready for web APIs!")
    
    return data


def demo_model_config():
    """Demo: Model configuration information."""
    print("\n" + "="*60)
    print("DEMO: ModelConfig")
    print("="*60)
    
    models = [
        "veo-3.0-fast-generate-preview",
        "veo-3.0-generate-preview",
        "veo-2.0-generate-001"
    ]
    
    for model in models:
        config = veo.ModelConfig.get_config(model)
        print(f"\n{config['name']}:")
        print(f"   Supports Duration: {config['supports_duration']}")
        print(f"   Supports Audio: {config['supports_audio']}")
        print(f"   Default Duration: {config['default_duration']}s")
        print(f"   Est. Generation Time: {config['generation_time']}s")


def demo_storage_manager():
    """Demo: Storage management."""
    print("\n" + "="*60)
    print("DEMO: StorageManager")
    print("="*60)
    
    storage = veo.StorageManager()
    
    print("Storage Directories:")
    print(f"   Videos: {storage.videos_dir}")
    print(f"   Frames: {storage.frames_dir}")
    print(f"   Temp: {storage.temp_dir}")
    
    video_path = storage.get_video_path("test.mp4")
    frame_path = storage.get_frame_path("test.jpg")
    
    print(f"\nPath Examples:")
    print(f"   Video: {video_path}")
    print(f"   Frame: {frame_path}")
    
    storage.cleanup_temp()
    print("\nTemp directory cleaned")


def main():
    """Run all demos."""
    print("="*60)
    print("VEO TOOLS SDK - Complete Function Demo")
    print("="*60)
    
    veo.init()
    
    print("\nAvailable Demos:")
    print("1. generate_from_text - Generate video from text")
    print("2. generate_from_image - Generate video from image")
    print("3. generate_from_video - Continue existing video")
    print("4. extract_frame - Extract single frame")
    print("5. extract_frames - Extract multiple frames")
    print("6. get_video_info - Get video metadata")
    print("7. stitch_videos - Stitch videos together")
    print("8. create_transition_points - Extract transition frames")
    print("9. Bridge - Workflow chaining")
    print("10. VideoResult - JSON serialization")
    print("11. ModelConfig - Model information")
    print("12. StorageManager - File management")
    print("0. Run all (except generation)")
    
    choice = input("\nSelect demo (0-12): ").strip()
    
    if choice == "1":
        demo_generate_from_text()
    elif choice == "2":
        demo_generate_from_image()
    elif choice == "3":
        demo_generate_from_video()
    elif choice == "4":
        demo_extract_frame()
    elif choice == "5":
        demo_extract_frames()
    elif choice == "6":
        demo_get_video_info()
    elif choice == "7":
        demo_stitch_videos()
    elif choice == "8":
        demo_create_transition_points()
    elif choice == "9":
        demo_bridge_basic()
    elif choice == "10":
        demo_videoResult_serialization()
    elif choice == "11":
        demo_model_config()
    elif choice == "12":
        demo_storage_manager()
    elif choice == "0":
        print("\nRunning all non-generation demos...")
        demo_extract_frame()
        demo_extract_frames()
        demo_get_video_info()
        demo_stitch_videos()
        demo_create_transition_points()
        demo_videoResult_serialization()
        demo_model_config()
        demo_storage_manager()
    else:
        print("Invalid choice")
    
    print("\n" + "="*60)
    print("Demo Complete!")
    print("="*60)


if __name__ == "__main__":
    main()