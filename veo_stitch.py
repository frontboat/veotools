#!/usr/bin/env python3
"""
Simplified video stitching script using Veo 3.0
Generates seamless video sequences by using frames from previous segments
"""

import os
import time
import tempfile
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


class VeoStitcher:
    def __init__(self, model: str = 'veo-3.0-fast-generate-preview'):
        """Initialize with Veo 3.0 fast model by default."""
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in .env file")
        
        self.client = genai.Client(api_key=api_key)
        self.model = f"models/{model}" if not model.startswith("models/") else model
        
        # Create output directory
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_video(self, prompt: str, image: Optional[types.Image] = None, 
                      duration_seconds: int = 5) -> types.Video:
        """Generate a video from prompt and optional image.
        
        Model capabilities:
        - Veo 3.0: Basic generation only (no duration/enhance control)
        - Veo 2.0: Full control (duration, enhance_prompt, fps)
        """
        
        if 'veo-3.0' in self.model:
            # Veo 3.0 preview models - limited parameters available
            config = types.GenerateVideosConfig(
                number_of_videos=1,
            )
        else:
            # Veo 2.0 - full parameter support
            config = types.GenerateVideosConfig(
                number_of_videos=1,
                duration_seconds=duration_seconds,
                enhance_prompt=True,
            )
        
        if image:
            operation = self.client.models.generate_videos(
                model=self.model,
                prompt=prompt,
                image=image,
                config=config
            )
        else:
            operation = self.client.models.generate_videos(
                model=self.model,
                prompt=prompt,
                config=config
            )
        
        return self._wait_for_video(operation)
    
    def _wait_for_video(self, operation) -> types.Video:
        """Poll until video is ready."""
        start_time = time.time()
        
        while not operation.done:
            elapsed = time.time() - start_time
            print(f"  Generating... ({elapsed:.0f}s)", end='\r')
            time.sleep(15)  # Poll every 15 seconds
            operation = self.client.operations.get(operation)
        
        total_time = time.time() - start_time
        print(f"  ✅ Generated ({total_time:.0f}s)        ")
        
        if operation.response and operation.response.generated_videos:
            return operation.response.generated_videos[0].video
        else:
            error_msg = "Video generation failed"
            if hasattr(operation, 'error'):
                error_msg += f": {operation.error}"
            raise RuntimeError(error_msg)
    
    def save_video(self, video: types.Video, filename: str) -> Path:
        """Save video to output directory."""
        filepath = self.output_dir / filename
        
        # For Gemini Developer API, videos are stored as files
        # We need to download them using the Files API
        if hasattr(video, 'uri') and video.uri:
            # Extract file ID from URI
            # URI format: https://generativelanguage.googleapis.com/v1beta/files/FILE_ID:download?alt=media
            import re
            match = re.search(r'/files/([^:]+)', video.uri)
            if match:
                file_id = match.group(1)
                file_name = f"files/{file_id}"
                
                try:
                    # Download using the Files API
                    file_data = self.client.files.get(name=file_name)
                    
                    # Try to download the actual content
                    import requests
                    headers = {
                        'x-goog-api-key': os.getenv('GEMINI_API_KEY')
                    }
                    response = requests.get(video.uri, headers=headers)
                    response.raise_for_status()
                    
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    
                    return filepath
                    
                except Exception as e:
                    # Store the URI for manual download if needed
                    uri_file = filepath.with_suffix('.txt')
                    with open(uri_file, 'w') as f:
                        f.write(f"Video URI: {video.uri}\n")
                    print(f"  ⚠️ Download failed, URI saved to: {uri_file.name}")
                    return filepath
            
        elif hasattr(video, 'data') and video.data:
            # Local video data
            with open(filepath, 'wb') as f:
                f.write(video.data)
            print(f"Saved: {filepath}")
            return filepath
        else:
            # Try to understand what we have
            print(f"Video object attributes: {dir(video)}")
            if hasattr(video, '__dict__'):
                print(f"Video object dict: {video.__dict__}")
            raise RuntimeError(f"Unable to save video - no URI or data found")
    
    def extract_frame_at_time(self, video_path: Path, time_from_end: float = 1.0) -> Path:
        """Extract a frame from video at specified seconds before the end."""
        import cv2
        
        cap = cv2.VideoCapture(str(video_path))
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        
        # Calculate frame position (1 second before end)
        target_time = max(0, duration - time_from_end)
        target_frame = int(target_time * fps)
        
        # Seek to target frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            raise RuntimeError(f"Failed to extract frame from {video_path}")
        
        # Save frame as image
        frame_path = self.output_dir / f"frame_{video_path.stem}_at_{target_time:.1f}s.jpg"
        cv2.imwrite(str(frame_path), frame)
        
        return frame_path
    
    def generate_sequence(self, initial_prompt: str, num_segments: int = 3,
                         duration: int = 5, continuation_prompt: Optional[str] = None):
        """Generate a sequence of stitched videos."""
        
        videos = []
        frames = []
        
        # Generate first video
        print(f"\n[1/{num_segments}] {initial_prompt[:50]}...")
        video = self.generate_video(initial_prompt, duration_seconds=duration)
        video_path = self.save_video(video, f"segment_1.mp4")
        videos.append(video_path)
        
        # Generate subsequent segments using frames from previous videos
        for i in range(2, num_segments + 1):
            prev_video = videos[-1]
            if prev_video.exists() and prev_video.stat().st_size > 0:
                try:
                    # Extract frame from previous video
                    frame_path = self.extract_frame_at_time(prev_video, time_from_end=1.0)
                    frames.append(frame_path)
                    
                    # Create Image object from frame
                    frame_image = types.Image.from_file(location=str(frame_path))
                    
                    # Generate next video using the frame
                    prompt = continuation_prompt if continuation_prompt else initial_prompt
                    print(f"\n[{i}/{num_segments}] From frame + '{prompt[:50]}...'")
                    
                    video = self.generate_video(prompt, image=frame_image, duration_seconds=duration)
                    video_path = self.save_video(video, f"segment_{i}.mp4")
                    videos.append(video_path)
                    
                except Exception as e:
                    # Fallback: generate without frame
                    print(f"\n[{i}/{num_segments}] {continuation_prompt[:50] if continuation_prompt else initial_prompt[:50]}... (text only)")
                    prompt = continuation_prompt if continuation_prompt else initial_prompt
                    video = self.generate_video(prompt, duration_seconds=duration)
                    video_path = self.save_video(video, f"segment_{i}.mp4")
                    videos.append(video_path)
            else:
                # Generate without frame
                print(f"\n[{i}/{num_segments}] {continuation_prompt[:50] if continuation_prompt else initial_prompt[:50]}... (text only)")
                prompt = continuation_prompt if continuation_prompt else initial_prompt
                video = self.generate_video(prompt, duration_seconds=duration)
                video_path = self.save_video(video, f"segment_{i}.mp4")
                videos.append(video_path)
        
        # Stitch videos together if we have multiple valid videos
        valid_videos = [v for v in videos if v.exists() and v.stat().st_size > 0]
        
        if len(valid_videos) > 1:
            print(f"\nStitching {len(valid_videos)} videos...")
            output_path = self.stitch_videos(valid_videos)
            print(f"\n✅ Complete: {output_path}")
        else:
            print(f"\n✅ Generated {len(valid_videos)} video(s) in {self.output_dir}")
        
        return videos
    
    def stitch_videos(self, video_paths: list) -> Path:
        """Stitch multiple videos together, trimming overlap."""
        import cv2
        
        output_path = self.output_dir / "stitched_final.mp4"
        
        # Get properties from first video
        cap = cv2.VideoCapture(str(video_paths[0]))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
        
        # Process each video
        for i, video_path in enumerate(video_paths):
            is_last_video = (i == len(video_paths) - 1)
            
            cap = cv2.VideoCapture(str(video_path))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Calculate frames to use
            # For all videos except the last, trim 1 second from the end
            if not is_last_video:
                frames_to_trim = int(fps * 1.0)  # 1 second worth of frames
                frames_to_use = max(1, total_frames - frames_to_trim)
            else:
                frames_to_use = total_frames
            
            frame_count = 0
            while frame_count < frames_to_use:
                ret, frame = cap.read()
                if not ret:
                    break
                out.write(frame)
                frame_count += 1
            
            cap.release()
            print(f"  Segment {i+1}: {frame_count} frames", end='\r')
        
        out.release()
        
        return output_path


def main():
    """Main execution."""
    print("🎬 Veo Video Stitcher")
    print("=" * 60)
    
    # Let user choose model
    print("\nAvailable models:")
    print("1. veo-3.0-fast-generate-preview")
    print("   ├─ Speed: ~1 min per video")
    print("   └─ Features: Basic generation (no duration/enhance control)")
    print("")
    print("2. veo-3.0-generate-preview")
    print("   ├─ Speed: ~1-2 min per video") 
    print("   └─ Features: Higher quality (no duration/enhance control)")
    print("")
    print("3. veo-2.0-generate-001")
    print("   ├─ Speed: ~2-3 min per video")
    print("   └─ Features: Full control (duration, enhance_prompt, fps)")
    
    choice = input("\nSelect model (1-3, default=1): ").strip() or "1"
    
    model_map = {
        "1": "veo-3.0-fast-generate-preview",
        "2": "veo-3.0-generate-preview",
        "3": "veo-2.0-generate-001"
    }
    
    model = model_map.get(choice, "veo-3.0-fast-generate-preview")
    
    # Get number of segments
    num_input = input("\nNumber of video segments to generate (1-5, default=2): ").strip() or "2"
    try:
        num_segments = min(5, max(1, int(num_input)))
    except:
        num_segments = 2
    
    # Configure prompts
    print("\nDefault prompt: 'A glowing neon cat driving a sports car through a cyberpunk city'")
    custom = input("Use custom prompt? (y/n, default=n): ").strip().lower()
    
    if custom == 'y':
        initial_prompt = input("Initial prompt: ").strip()
        if num_segments > 1:
            continuation_prompt = input("Continuation prompt (optional): ").strip() or initial_prompt
        else:
            continuation_prompt = initial_prompt
    else:
        initial_prompt = "A glowing neon cat driving a sports car at top speed through a cyberpunk city at night"
        continuation_prompt = "The neon cat continues driving through the cyberpunk city"
    
    # Duration (only for Veo 2.0)
    duration = 5
    if "2.0" in model:
        dur_input = input("\nVideo duration in seconds (3-10, default=5): ").strip() or "5"
        try:
            duration = min(10, max(3, int(dur_input)))
        except:
            duration = 5
    
    try:
        stitcher = VeoStitcher(model=model)
        
        print(f"\n{'='*60}")
        print(f"Configuration:")
        print(f"  Model: {model}")
        print(f"  Segments: {num_segments}")
        
        # Show model-specific features
        if "2.0" in model:
            print(f"  Duration: {duration}s per segment (configurable)")
            print(f"  Enhance Prompt: ✅ Enabled")
        else:
            print(f"  Duration: Model default (~5-8s)")
            print(f"  Enhance Prompt: ❌ Not available")
        
        print(f"  Initial: {initial_prompt[:60]}{'...' if len(initial_prompt) > 60 else ''}")
        if num_segments > 1:
            print(f"  Continue: {continuation_prompt[:60]}{'...' if len(continuation_prompt) > 60 else ''}")
            print(f"  Stitching: Will trim 1s overlap between segments")
        print(f"{'='*60}")
        
        confirm = input("\nGenerate video sequence? (y/n, default=y): ").strip().lower()
        
        if confirm != 'n':
            videos = stitcher.generate_sequence(
                initial_prompt=initial_prompt,
                num_segments=num_segments,
                duration=duration,
                continuation_prompt=continuation_prompt
            )
            
        else:
            print("Cancelled.")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()