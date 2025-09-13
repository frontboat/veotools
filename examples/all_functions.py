#!/usr/bin/env python3
"""Comprehensive demonstration of all Veo Tools SDK functions.

This example showcases every function available in the SDK with practical examples.
Each demo can be run independently to understand specific functionality.

Usage:
    python examples/all_functions.py                  # Interactive menu
    python examples/all_functions.py --demo text      # Run specific demo
    python examples/all_functions.py --list           # List all demos
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import json
import time
import veotools as veo


class DemoRunner:
    """Runner for SDK function demonstrations."""
    
    def __init__(self):
        self.demos = {
            "text": ("Generate video from text", self.demo_text_generation),
            "image": ("Generate video from image", self.demo_image_generation),
            "video": ("Continue video from frame", self.demo_video_continuation),
            "extract": ("Extract frames from video", self.demo_frame_extraction),
            "info": ("Get video metadata", self.demo_video_info),
            "stitch": ("Stitch videos together", self.demo_video_stitching),
            "bridge": ("Bridge workflow API", self.demo_bridge_workflow),
            "models": ("List available models", self.demo_model_listing),
            "storage": ("Storage management", self.demo_storage_management),
            "result": ("VideoResult serialization", self.demo_result_serialization),
            "async": ("Async job management", self.demo_async_generation),
            "safety": ("Safety settings", self.demo_safety_settings),
            "cache": ("Context caching", self.demo_context_caching),
        }
        self.model = None
    
    def _get_model(self):
        """Get or select a model for generation."""
        if not self.model:
            models = veo.list_models(include_remote=True)["models"]
            veo_models = [m for m in models if m["id"].startswith("veo-")]
            self.model = next((m["id"] for m in veo_models if "fast" in m["id"]), 
                             "veo-3.0-fast-generate-preview")
        return self.model
    
    def demo_text_generation(self):
        """Generate video from text prompt."""
        print("\n📝 Text-to-Video Generation")
        print("-" * 40)
        
        model = self._get_model()
        prompt = "A serene lake at sunset with rippling water"
        
        print(f"Prompt: {prompt}")
        print(f"Model: {model}")
        
        result = veo.generate_from_text(
            prompt=prompt,
            model=model,
            on_progress=lambda msg, pct: print(f"  {msg}: {pct}%")
        )
        
        print(f"\n✓ Generated: {result.path}")
        print(f"  Duration: {result.metadata.duration:.1f}s")
        print(f"  Resolution: {result.metadata.width}x{result.metadata.height}")
        
        return result
    
    def demo_image_generation(self):
        """Generate video from an image."""
        print("\n🖼️ Image-to-Video Generation")
        print("-" * 40)
        
        # Find or create an image
        images = []
        for ext in ['*.jpg', '*.jpeg', '*.png']:
            images.extend(Path(".").glob(ext))
        
        if not images:
            # Extract frame from existing video if available
            videos = list(Path("output/videos").glob("*.mp4"))
            if videos:
                print("No images found, extracting frame from video...")
                image_path = veo.extract_frame(videos[0], time_offset=1.0)
            else:
                print("No images or videos found. Run text generation demo first.")
                return None
        else:
            image_path = images[0]
        
        model = self._get_model()
        prompt = "Bring the scene to life with natural movement"
        
        print(f"Image: {image_path}")
        print(f"Prompt: {prompt}")
        print(f"Model: {model}")
        
        result = veo.generate_from_image(
            image_path=image_path,
            prompt=prompt,
            model=model,
            on_progress=lambda msg, pct: print(f"  {msg}: {pct}%")
        )
        
        print(f"\n✓ Generated: {result.path}")
        print(f"  Duration: {result.metadata.duration:.1f}s")
        
        return result
    
    def demo_video_continuation(self):
        """Continue a video from a specific frame."""
        print("\n🎬 Video Continuation")
        print("-" * 40)
        
        videos = list(Path("output/videos").glob("*.mp4"))
        if not videos:
            print("No videos found. Generate one first with text demo.")
            return None
        
        video_path = videos[0]
        model = self._get_model()
        prompt = "Camera pulls back to reveal a wider landscape"
        
        print(f"Source: {video_path.name}")
        print(f"Prompt: {prompt}")
        print(f"Model: {model}")
        print(f"Extract from: last frame")
        
        result = veo.generate_from_video(
            video_path=video_path,
            prompt=prompt,
            extract_at=-1.0,  # Last frame
            model=model,
            on_progress=lambda msg, pct: print(f"  {msg}: {pct}%")
        )
        
        print(f"\n✓ Continuation: {result.path}")
        print(f"  Duration: {result.metadata.duration:.1f}s")
        
        return result
    
    def demo_frame_extraction(self):
        """Extract frames from video at specific times."""
        print("\n🎞️ Frame Extraction")
        print("-" * 40)
        
        videos = list(Path("output/videos").glob("*.mp4"))
        if not videos:
            print("No videos found. Generate one first.")
            return None
        
        video = videos[0]
        info = veo.get_video_info(video)
        
        print(f"Video: {video.name}")
        print(f"Duration: {info['duration']:.1f}s")
        
        # Extract single frame
        print("\nExtracting single frame at 1.0s...")
        frame = veo.extract_frame(video, time_offset=1.0)
        print(f"✓ Saved: {frame}")
        
        # Extract multiple frames
        print("\nExtracting multiple frames...")
        times = [0.0, info['duration']/2, -1.0]  # Start, middle, end
        frames = veo.extract_frames(video, times)
        
        for i, frame_path in enumerate(frames):
            print(f"✓ Frame {i+1}: {frame_path.name}")
        
        # Extract transition points between two videos
        if len(videos) >= 2:
            print("\nExtracting transition points...")
            frame_a, frame_b = veo.create_transition_points(
                videos[0], videos[1],
                extract_points={"a_end": -1.0, "b_start": 0.0}
            )
            print(f"✓ Video A end: {frame_a.name}")
            print(f"✓ Video B start: {frame_b.name}")
        
        return frames
    
    def demo_video_info(self):
        """Get detailed video metadata."""
        print("\n📊 Video Information")
        print("-" * 40)
        
        videos = list(Path("output/videos").glob("*.mp4"))
        if not videos:
            print("No videos found. Generate one first.")
            return None
        
        video = videos[0]
        print(f"Analyzing: {video.name}\n")
        
        info = veo.get_video_info(video)
        
        print("Metadata:")
        print(f"  Resolution: {info['width']}x{info['height']}")
        print(f"  Duration: {info['duration']:.2f} seconds")
        print(f"  FPS: {info['fps']}")
        print(f"  Frame Count: {info['frame_count']}")
        print(f"  Codec: {info.get('codec', 'N/A')}")
        print(f"  Bitrate: {info.get('bitrate', 'N/A')}")
        
        return info
    
    def demo_video_stitching(self):
        """Stitch multiple videos together."""
        print("\n🔗 Video Stitching")
        print("-" * 40)
        
        videos = list(Path("output/videos").glob("*.mp4"))
        if len(videos) < 2:
            print("Need at least 2 videos. Generating samples...")
            
            # Generate two videos
            v1 = veo.generate_from_text(
                "Ocean waves crashing on beach",
                model=self._get_model(),
                on_progress=lambda msg, pct: print(f"  Video 1 - {msg}: {pct}%")
            )
            
            v2 = veo.generate_from_text(
                "Sunset over the ocean horizon",
                model=self._get_model(),
                on_progress=lambda msg, pct: print(f"  Video 2 - {msg}: {pct}%")
            )
            
            videos = [v1.path, v2.path]
        else:
            videos = videos[:2]
        
        print(f"\nStitching {len(videos)} videos:")
        for v in videos:
            print(f"  - {v.name}")
        
        result = veo.stitch_videos(
            video_paths=videos,
            overlap=1.0,
            on_progress=lambda msg, pct: print(f"  {msg}: {pct}%")
        )
        
        print(f"\n✓ Stitched: {result.path}")
        print(f"  Duration: {result.metadata.duration:.1f}s")
        print(f"  Transitions: Seamless with 1.0s overlap")
        
        return result
    
    def demo_bridge_workflow(self):
        """Demonstrate Bridge workflow API."""
        print("\n🌉 Bridge Workflow API")
        print("-" * 40)
        
        model = self._get_model()
        
        print("Creating multi-scene workflow...")
        print(f"Model: {model}\n")
        
        bridge = veo.Bridge("demo_workflow")
        
        # Build workflow
        result = (bridge
            .with_progress(lambda msg, pct: print(f"  {msg}: {pct}%"))
            .generate("Morning: City skyline at dawn", model=model)
            .generate("Afternoon: Busy city streets", model=model)
            .generate("Evening: City lights turning on", model=model)
            .stitch(overlap=1.0)
            .save("output/videos/city_timelapse.mp4")
        )
        
        print(f"\n✓ Workflow complete: {result}")
        
        # Export workflow
        workflow = bridge.to_dict()
        print(f"\nWorkflow structure:")
        print(f"  ID: {workflow['id']}")
        print(f"  Name: {workflow['name']}")
        print(f"  Steps: {len(workflow['steps'])}")
        
        for i, step in enumerate(workflow['steps'], 1):
            action = step['action']
            if action == 'generate':
                prompt = step['params']['prompt'][:30] + "..."
                print(f"    {i}. {action}: {prompt}")
            else:
                print(f"    {i}. {action}")
        
        return bridge
    
    def demo_model_listing(self):
        """List and inspect available models."""
        print("\n🤖 Model Information")
        print("-" * 40)
        
        # List local models
        print("Local models:")
        local = veo.list_models()
        for model in local["models"]:
            print(f"  - {model['id']}")
        
        # List all models including remote
        print("\nAll available models:")
        all_models = veo.list_models(include_remote=True)
        
        veo_models = [m for m in all_models["models"] if m["id"].startswith("veo-")]
        
        for model in veo_models:
            model_id = model["id"]
            config = veo.ModelConfig.get_config(model_id)
            
            print(f"\n  {config['name']}:")
            print(f"    ID: {model_id}")
            print(f"    Duration: {config['default_duration']}s")
            print(f"    Supports custom duration: {config['supports_duration']}")
            print(f"    Supports audio: {config['supports_audio']}")
            print(f"    Generation time: ~{config['generation_time']}s")
        
        return all_models
    
    def demo_storage_management(self):
        """Demonstrate storage and file management."""
        print("\n📁 Storage Management")
        print("-" * 40)
        
        storage = veo.StorageManager()
        
        print("Output directories:")
        print(f"  Base: {storage.output_dir}")
        print(f"  Videos: {storage.videos_dir}")
        print(f"  Frames: {storage.frames_dir}")
        print(f"  Temp: {storage.temp_dir}")
        
        # Count files
        video_count = len(list(storage.videos_dir.glob("*.mp4")))
        frame_count = len(list(storage.frames_dir.glob("*.jpg")))
        
        print(f"\nCurrent storage:")
        print(f"  Videos: {video_count} files")
        print(f"  Frames: {frame_count} files")
        
        # Demonstrate path generation
        print(f"\nPath generation examples:")
        print(f"  Video: {storage.get_video_path('example.mp4')}")
        print(f"  Frame: {storage.get_frame_path('frame.jpg')}")
        print(f"  Temp: {storage.get_temp_path('processing.tmp')}")
        
        # Clean temp
        storage.cleanup_temp()
        print(f"\n✓ Temp directory cleaned")
        
        return storage
    
    def demo_result_serialization(self):
        """Demonstrate VideoResult serialization."""
        print("\n📄 VideoResult Serialization")
        print("-" * 40)
        
        # Create a sample result
        result = veo.VideoResult()
        result.id = "demo_12345"
        result.prompt = "A beautiful sunset over mountains"
        result.model = "veo-3.0-fast-generate-preview"
        result.path = Path("output/videos/sunset.mp4")
        result.url = f"file://{result.path.absolute()}"
        result.status = veo.VideoStatus.COMPLETED
        
        # Add metadata
        result.metadata.width = 1024
        result.metadata.height = 576
        result.metadata.duration = 8.0
        result.metadata.fps = 24.0
        result.metadata.frame_count = 192
        
        # Simulate progress updates
        result.update_progress("Initializing", 0)
        result.update_progress("Generating", 50)
        result.update_progress("Finalizing", 90)
        result.update_progress("Complete", 100)
        
        # Serialize to dict
        data = result.to_dict()
        
        print("VideoResult as JSON:")
        print(json.dumps(data, indent=2, default=str))
        
        print("\n✓ Ready for web API responses")
        
        return result
    
    def demo_async_generation(self):
        """Demonstrate async job management."""
        print("\n⚡ Async Job Management")
        print("-" * 40)
        
        model = self._get_model()
        prompt = "Lightning storm over mountains"
        
        print(f"Starting async generation...")
        print(f"  Prompt: {prompt}")
        print(f"  Model: {model}")
        
        # Start async generation
        job_id = veo.generate_start(
            prompt=prompt,
            model=model
        )
        
        print(f"\n✓ Job started: {job_id}")
        
        # Check status
        print("\nChecking status...")
        for i in range(5):
            result = veo.generate_get(job_id)
            print(f"  Attempt {i+1}: {result.status.value}")
            
            if result.status == veo.VideoStatus.COMPLETED:
                print(f"\n✓ Complete: {result.path}")
                return result
            
            time.sleep(2)
        
        # Cancel if still running
        print("\nCancelling job...")
        veo.generate_cancel(job_id)
        print("✓ Job cancelled")
        
        return job_id
    
    def demo_safety_settings(self):
        """Demonstrate safety settings configuration."""
        print("\n🛡️ Safety Settings")
        print("-" * 40)
        
        print("Safety setting options:")
        print("  - BLOCK_NONE: No filtering")
        print("  - BLOCK_ONLY_HIGH: Block high-risk content")
        print("  - BLOCK_MEDIUM_AND_ABOVE: Block medium and high risk")
        print("  - BLOCK_LOW_AND_ABOVE: Block all flagged content")
        
        print("\nExample configuration:")
        safety_settings = {
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_MEDIUM_AND_ABOVE",
            "HARM_CATEGORY_HARASSMENT": "BLOCK_MEDIUM_AND_ABOVE",
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_ONLY_HIGH"
        }
        
        print(json.dumps(safety_settings, indent=2))
        
        print("\nUsage in generation:")
        print("  result = veo.generate_from_text(")
        print("      prompt='...',")
        print("      safety_settings=safety_settings")
        print("  )")
        
        return safety_settings
    
    def demo_context_caching(self):
        """Demonstrate context caching for efficiency."""
        print("\n💾 Context Caching")
        print("-" * 40)
        
        print("Context caching improves efficiency for:")
        print("  - Repeated operations on same media")
        print("  - Multiple generations from same source")
        print("  - Batch processing workflows")
        
        videos = list(Path("output/videos").glob("*.mp4"))
        if not videos:
            print("\nNo videos available for caching demo.")
            return None
        
        video_path = videos[0]
        
        print(f"\nCreating cached content from: {video_path.name}")
        
        # Create cached content
        cached = veo.create_cached_content(
            video_path,
            ttl_seconds=3600  # Cache for 1 hour
        )
        
        print(f"✓ Cached with ID: {cached.name}")
        print(f"  TTL: 1 hour")
        
        print("\nUsage with cached content:")
        print("  result = veo.generate_from_video(")
        print("      video_path=video_path,")
        print("      prompt='...',")
        print("      cached_content=cached")
        print("  )")
        
        return cached
    
    def run_all(self):
        """Run all demos in sequence."""
        print("\n" + "="*60)
        print("Running all SDK demos")
        print("="*60)
        
        for key in ["models", "text", "extract", "info", "storage", "result"]:
            if key in self.demos:
                print(f"\n{'='*60}")
                self.demos[key][1]()
                input("\nPress Enter to continue...")
    
    def interactive_menu(self):
        """Show interactive menu for demo selection."""
        while True:
            print("\n" + "="*60)
            print("Veo Tools SDK - Function Demonstrations")
            print("="*60)
            
            print("\nAvailable demos:")
            for i, (key, (desc, _)) in enumerate(self.demos.items(), 1):
                print(f"  {i:2}. {desc} ({key})")
            
            print(f"\n   0. Run all (non-generation demos)")
            print(f"   q. Quit")
            
            choice = input("\nSelect demo: ").strip().lower()
            
            if choice == 'q':
                print("Goodbye!")
                break
            
            if choice == '0':
                self.run_all()
                continue
            
            # Handle numeric or key-based selection
            try:
                idx = int(choice) - 1
                keys = list(self.demos.keys())
                if 0 <= idx < len(keys):
                    key = keys[idx]
                else:
                    print("Invalid selection")
                    continue
            except ValueError:
                if choice in self.demos:
                    key = choice
                else:
                    print("Invalid selection")
                    continue
            
            # Run selected demo
            desc, func = self.demos[key]
            print(f"\n{'='*60}")
            try:
                func()
            except Exception as e:
                print(f"\nError: {e}")
            
            input("\nPress Enter to continue...")


def main():
    parser = argparse.ArgumentParser(description="Comprehensive SDK demonstration")
    parser.add_argument("--demo", choices=list(DemoRunner().demos.keys()),
                        help="Run specific demo")
    parser.add_argument("--list", action="store_true",
                        help="List all available demos")
    parser.add_argument("--all", action="store_true",
                        help="Run all non-generation demos")
    
    args = parser.parse_args()
    
    veo.init()
    runner = DemoRunner()
    
    if args.list:
        print("\nAvailable demos:")
        for key, (desc, _) in runner.demos.items():
            print(f"  {key:12} - {desc}")
    elif args.demo:
        desc, func = runner.demos[args.demo]
        print(f"\nRunning: {desc}")
        func()
    elif args.all:
        runner.run_all()
    else:
        runner.interactive_menu()


if __name__ == "__main__":
    main()