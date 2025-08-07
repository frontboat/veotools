"""Seamless video stitching for Veo Tools."""

import cv2
from pathlib import Path
from typing import List, Optional, Callable

from ..core import StorageManager, ProgressTracker
from ..models import VideoResult, VideoMetadata
from ..process.extractor import get_video_info


def stitch_videos(
    video_paths: List[Path],
    overlap: float = 1.0,
    output_path: Optional[Path] = None,
    on_progress: Optional[Callable] = None
) -> VideoResult:
    if not video_paths:
        raise ValueError("No videos provided to stitch")
    
    storage = StorageManager()
    progress = ProgressTracker(on_progress)
    result = VideoResult()
    
    try:
        progress.start("Preparing")
        
        for path in video_paths:
            if not path.exists():
                raise FileNotFoundError(f"Video not found: {path}")
        
        first_info = get_video_info(video_paths[0])
        fps = first_info["fps"]
        width = first_info["width"]
        height = first_info["height"]
        
        if output_path is None:
            filename = f"stitched_{result.id[:8]}.mp4"
            output_path = storage.get_video_path(filename)
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        temp_path = output_path.parent / f"temp_{output_path.name}"
        out = cv2.VideoWriter(str(temp_path), fourcc, fps, (width, height))
        
        total_frames_written = 0
        total_videos = len(video_paths)
        
        for i, video_path in enumerate(video_paths):
            is_last_video = (i == total_videos - 1)
            percent = int((i / total_videos) * 90)
            progress.update(f"Processing {i+1}/{total_videos}", percent)
            
            cap = cv2.VideoCapture(str(video_path))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if not is_last_video and overlap > 0:
                frames_to_trim = int(fps * overlap)
                frames_to_use = max(1, total_frames - frames_to_trim)
            else:
                frames_to_use = total_frames
            
            frame_count = 0
            while frame_count < frames_to_use:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame.shape[1] != width or frame.shape[0] != height:
                    frame = cv2.resize(frame, (width, height))
                
                out.write(frame)
                frame_count += 1
                total_frames_written += 1
            
            cap.release()
        
        out.release()
        
        import subprocess
        try:
            cmd = [
                "ffmpeg", "-i", str(temp_path),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y",
                str(output_path)
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            temp_path.unlink()
        except subprocess.CalledProcessError:
            import shutil
            shutil.move(str(temp_path), str(output_path))
        
        result.path = output_path
        result.url = storage.get_url(output_path)
        result.metadata = VideoMetadata(
            fps=fps,
            duration=total_frames_written / fps if fps > 0 else 0,
            width=width,
            height=height
        )
        
        progress.complete("Complete")
        result.update_progress("Complete", 100)
        
    except Exception as e:
        result.mark_failed(e)
        raise
    
    return result


def stitch_with_transitions(
    video_paths: List[Path],
    transition_videos: List[Path],
    output_path: Optional[Path] = None,
    on_progress: Optional[Callable] = None
) -> VideoResult:
    if len(transition_videos) != len(video_paths) - 1:
        raise ValueError(f"Need {len(video_paths)-1} transitions for {len(video_paths)} videos")
    
    combined_paths = []
    for i, video in enumerate(video_paths[:-1]):
        combined_paths.append(video)
        combined_paths.append(transition_videos[i])
    combined_paths.append(video_paths[-1])
    
    return stitch_videos(
        combined_paths,
        overlap=0,
        output_path=output_path,
        on_progress=on_progress
    )


def create_transition_points(
    video_a: Path,
    video_b: Path,
    extract_points: Optional[dict] = None
) -> tuple:
    from ..process.extractor import extract_frame
    
    if extract_points is None:
        extract_points = {
            "a_end": -1.0,
            "b_start": 1.0
        }
    
    frame_a = extract_frame(video_a, extract_points.get("a_end", -1.0))
    frame_b = extract_frame(video_b, extract_points.get("b_start", 1.0))
    
    return frame_a, frame_b