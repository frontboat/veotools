"""Frame extraction and video info utilities for Veo Tools.

Enhancements:
- `get_video_info` now first attempts to use `ffprobe` for accurate metadata
  (fps, duration, width, height). If `ffprobe` is unavailable, it falls back
  to OpenCV-based probing.
"""

import cv2
import json
import subprocess
from pathlib import Path
from typing import Optional

from ..core import StorageManager


def extract_frame(
    video_path: Path,
    time_offset: float = -1.0,
    output_path: Optional[Path] = None
) -> Path:
    """Extract a single frame from a video at the specified time offset.

    Extracts and saves a frame from a video file as a JPEG image. Supports both
    positive time offsets (from start) and negative offsets (from end). Uses
    OpenCV for video processing and automatically manages storage paths.

    Args:
        video_path: Path to the input video file.
        time_offset: Time in seconds where to extract the frame. Positive values
            are from the start, negative values from the end. Defaults to -1.0
            (1 second from the end).
        output_path: Optional custom path for saving the extracted frame. If None,
            auto-generates a path using StorageManager.

    Returns:
        Path: The path where the extracted frame was saved.

    Raises:
        FileNotFoundError: If the input video file doesn't exist.
        RuntimeError: If frame extraction fails (e.g., invalid time offset).

    Examples:
        Extract the last frame:
        >>> frame_path = extract_frame(Path("video.mp4"))
        >>> print(f"Frame saved to: {frame_path}")

        Extract frame at 5 seconds:
        >>> frame_path = extract_frame(Path("video.mp4"), time_offset=5.0)

        Extract with custom output path:
        >>> custom_path = Path("my_frame.jpg")
        >>> frame_path = extract_frame(
        ...     Path("video.mp4"),
        ...     time_offset=10.0,
        ...     output_path=custom_path
        ... )
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    
    storage = StorageManager()
    cap = cv2.VideoCapture(str(video_path))
    
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        if time_offset < 0:
            target_time = max(0, duration + time_offset)
        else:
            target_time = min(duration, time_offset)
        
        target_frame = int(target_time * fps)
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame = cap.read()
        
        if not ret:
            raise RuntimeError(f"Failed to extract frame at {target_time:.1f}s")
        
        if output_path is None:
            filename = f"frame_{video_path.stem}_at_{target_time:.1f}s.jpg"
            output_path = storage.get_frame_path(filename)
        
        cv2.imwrite(str(output_path), frame)
        
        return output_path
        
    finally:
        cap.release()


def extract_frames(
    video_path: Path,
    times: list,
    output_dir: Optional[Path] = None
) -> list:
    """Extract multiple frames from a video at specified time offsets.

    Extracts and saves multiple frames from a video file as JPEG images. Each
    time offset can be positive (from start) or negative (from end). Uses
    OpenCV for efficient batch frame extraction.

    Args:
        video_path: Path to the input video file.
        times: List of time offsets in seconds. Each can be positive (from start)
            or negative (from end).
        output_dir: Optional directory for saving frames. If None, uses
            StorageManager's default frame directory.

    Returns:
        list: List of Path objects where the extracted frames were saved.
            Order matches the input times list.

    Raises:
        FileNotFoundError: If the input video file doesn't exist.

    Examples:
        Extract frames at multiple timestamps:
        >>> frame_paths = extract_frames(
        ...     Path("video.mp4"),
        ...     [0.0, 5.0, 10.0, -1.0]  # Start, 5s, 10s, and 1s from end
        ... )
        >>> print(f"Extracted {len(frame_paths)} frames")

        Extract to custom directory:
        >>> output_dir = Path("extracted_frames")
        >>> frame_paths = extract_frames(
        ...     Path("movie.mp4"),
        ...     [1.0, 2.0, 3.0],
        ...     output_dir=output_dir
        ... )

    Note:
        Failed frame extractions are silently skipped. The returned list may
        contain fewer paths than input times if some extractions fail.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    
    storage = StorageManager()
    cap = cv2.VideoCapture(str(video_path))
    frames = []
    
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        for i, time_offset in enumerate(times):
            if time_offset < 0:
                target_time = max(0, duration + time_offset)
            else:
                target_time = min(duration, time_offset)
            
            target_frame = int(target_time * fps)
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = cap.read()
            
            if ret:
                if output_dir:
                    output_path = output_dir / f"frame_{i:03d}_at_{target_time:.1f}s.jpg"
                else:
                    filename = f"frame_{video_path.stem}_{i:03d}_at_{target_time:.1f}s.jpg"
                    output_path = storage.get_frame_path(filename)
                
                cv2.imwrite(str(output_path), frame)
                frames.append(output_path)
        
        return frames
        
    finally:
        cap.release()


def get_video_info(video_path: Path) -> dict:
    """Extract comprehensive metadata from a video file.

    Retrieves video metadata including frame rate, duration, dimensions, and frame count.
    First attempts to use ffprobe for accurate metadata extraction, falling back to
    OpenCV if ffprobe is unavailable. This dual approach ensures maximum compatibility
    and accuracy.

    Args:
        video_path: Path to the input video file.

    Returns:
        dict: Video metadata containing:
            - fps (float): Frames per second
            - frame_count (int): Total number of frames
            - width (int): Video width in pixels
            - height (int): Video height in pixels
            - duration (float): Video duration in seconds

    Raises:
        FileNotFoundError: If the input video file doesn't exist.

    Examples:
        Get basic video information:
        >>> info = get_video_info(Path("video.mp4"))
        >>> print(f"Duration: {info['duration']:.2f}s")
        >>> print(f"Resolution: {info['width']}x{info['height']}")
        >>> print(f"Frame rate: {info['fps']} fps")

        Check if video has expected properties:
        >>> info = get_video_info(Path("movie.mp4"))
        >>> if info['fps'] > 30:
        ...     print("High frame rate video")
        >>> if info['width'] >= 1920:
        ...     print("HD or higher resolution")

    Note:
        - ffprobe (from FFmpeg) provides more accurate metadata when available
        - OpenCV fallback may have slight inaccuracies in frame rate calculation
        - All numeric values are guaranteed to be non-negative
        - Returns 0.0 for fps/duration if video properties cannot be determined
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    # Try ffprobe for precise metadata
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout or "{}")
        video_stream = None
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                video_stream = s
                break
        if video_stream:
            # FPS can be in r_frame_rate or avg_frame_rate as "num/den"
            fps_val = 0.0
            for key in ("avg_frame_rate", "r_frame_rate"):
                rate = video_stream.get(key)
                if isinstance(rate, str) and "/" in rate:
                    num, den = rate.split("/", 1)
                    try:
                        num_f, den_f = float(num), float(den)
                        if den_f > 0:
                            fps_val = num_f / den_f
                            break
                    except Exception:
                        pass
            width = int(video_stream.get("width", 0) or 0)
            height = int(video_stream.get("height", 0) or 0)
            duration = None
            # Prefer format duration
            if "format" in data and data["format"].get("duration"):
                try:
                    duration = float(data["format"]["duration"])  # seconds
                except Exception:
                    duration = None
            if duration is None and video_stream.get("duration"):
                try:
                    duration = float(video_stream["duration"])  # seconds
                except Exception:
                    duration = None
            frame_count = int(fps_val * duration) if fps_val and duration else 0
            return {
                "fps": fps_val or 0.0,
                "frame_count": frame_count,
                "width": width,
                "height": height,
                "duration": duration or 0.0,
            }
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        # Fall back to OpenCV below
        pass

    # Fallback: OpenCV probing
    cap = cv2.VideoCapture(str(video_path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps and fps > 0 else 0
        return {
            "fps": fps or 0.0,
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "duration": duration,
        }
    finally:
        cap.release()