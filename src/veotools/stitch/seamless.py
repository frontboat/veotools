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
    """Seamlessly stitch multiple videos together into a single continuous video.

    Combines multiple video files into one continuous video by concatenating them
    with optional overlap trimming. All videos are resized to match the dimensions
    of the first video. The output is optimized with H.264 encoding for broad
    compatibility.

    Args:
        video_paths: List of paths to video files to stitch together, in order.
        overlap: Duration in seconds to trim from the end of each video (except
            the last one) to create smooth transitions. Defaults to 1.0.
        output_path: Optional custom output path. If None, auto-generates a path
            using StorageManager.
        on_progress: Optional callback function called with progress updates (message, percent).

    Returns:
        VideoResult: Object containing the stitched video path, metadata, and operation details.

    Raises:
        ValueError: If no videos are provided or if fewer than 2 videos are found.
        FileNotFoundError: If any input video file doesn't exist.
        RuntimeError: If video processing fails.

    Examples:
        Stitch videos with default overlap:
        >>> video_files = [Path("part1.mp4"), Path("part2.mp4"), Path("part3.mp4")]
        >>> result = stitch_videos(video_files)
        >>> print(f"Stitched video: {result.path}")

        Stitch without overlap:
        >>> result = stitch_videos(video_files, overlap=0.0)

        Stitch with progress tracking:
        >>> def show_progress(msg, pct):
        ...     print(f"Stitching: {msg} ({pct}%)")
        >>> result = stitch_videos(
        ...     video_files,
        ...     overlap=2.0,
        ...     on_progress=show_progress
        ... )

        Custom output location:
        >>> result = stitch_videos(
        ...     video_files,
        ...     output_path=Path("final_movie.mp4")
        ... )

    Note:
        - Videos are resized to match the first video's dimensions
        - Uses H.264 encoding with CRF 23 for good quality/size balance
        - Automatically handles frame rate consistency
        - FFmpeg is used for final encoding if available, otherwise uses OpenCV
    """
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
    """Stitch videos together with custom transition videos between them.

    Combines multiple videos by inserting transition videos between each pair
    of main videos. The transitions are placed between consecutive videos to
    create smooth, cinematic connections between scenes.

    Args:
        video_paths: List of main video files to stitch together, in order.
        transition_videos: List of transition videos to insert between main videos.
            Must have exactly len(video_paths) - 1 transitions.
        output_path: Optional custom output path. If None, auto-generates a path
            using StorageManager.
        on_progress: Optional callback function called with progress updates (message, percent).

    Returns:
        VideoResult: Object containing the final stitched video with transitions.

    Raises:
        ValueError: If the number of transition videos doesn't match the requirement
            (should be one less than the number of main videos).
        FileNotFoundError: If any video file doesn't exist.

    Examples:
        Add transitions between three video clips:
        >>> main_videos = [Path("scene1.mp4"), Path("scene2.mp4"), Path("scene3.mp4")]
        >>> transitions = [Path("fade1.mp4"), Path("fade2.mp4")]
        >>> result = stitch_with_transitions(main_videos, transitions)
        >>> print(f"Final video with transitions: {result.path}")

        With progress tracking:
        >>> def track_progress(msg, pct):
        ...     print(f"Processing: {msg} - {pct}%")
        >>> result = stitch_with_transitions(
        ...     main_videos,
        ...     transitions,
        ...     on_progress=track_progress
        ... )

    Note:
        This function uses stitch_videos internally with overlap=0 to preserve
        transition videos exactly as provided.
    """
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
    """Extract frames from two videos to analyze potential transition points.

    Extracts representative frames from two videos that can be used to analyze
    how well they might transition together. Typically extracts the ending frame
    of the first video and the beginning frame of the second video.

    Args:
        video_a: Path to the first video file.
        video_b: Path to the second video file.
        extract_points: Optional dictionary specifying extraction points:
            - "a_end": Time offset for frame extraction from video_a (default: -1.0)
            - "b_start": Time offset for frame extraction from video_b (default: 1.0)
            If None, uses default values.

    Returns:
        tuple: A tuple containing (frame_a_path, frame_b_path) where:
            - frame_a_path: Path to extracted frame from video_a
            - frame_b_path: Path to extracted frame from video_b

    Raises:
        FileNotFoundError: If either video file doesn't exist.
        RuntimeError: If frame extraction fails for either video.

    Examples:
        Extract transition frames with defaults:
        >>> frame_a, frame_b = create_transition_points(
        ...     Path("clip1.mp4"),
        ...     Path("clip2.mp4")
        ... )
        >>> print(f"Transition frames: {frame_a}, {frame_b}")

        Custom extraction points:
        >>> points = {"a_end": -2.0, "b_start": 0.5}
        >>> frame_a, frame_b = create_transition_points(
        ...     Path("scene1.mp4"),
        ...     Path("scene2.mp4"),
        ...     extract_points=points
        ... )

    Note:
        - Default extracts 1 second before the end of video_a
        - Default extracts 1 second after the start of video_b
        - Negative values in extract_points count from the end of the video
        - These frames can be used to analyze color, composition, or content
          similarity for better transition planning
    """
    from ..process.extractor import extract_frame
    
    if extract_points is None:
        extract_points = {
            "a_end": -1.0,
            "b_start": 1.0
        }
    
    frame_a = extract_frame(video_a, extract_points.get("a_end", -1.0))
    frame_b = extract_frame(video_b, extract_points.get("b_start", 1.0))
    
    return frame_a, frame_b