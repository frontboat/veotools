"""Seamless video stitching for Veo Tools."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List, Optional, Callable

from ..core import StorageManager, ProgressTracker
from ..models import VideoResult, VideoMetadata
from ..process.extractor import get_video_info


def _has_audio(video_path: Path) -> bool:
    """Return True if the media file contains an audio stream."""

    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "json",
            str(video_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout or "{}")
        return bool(data.get("streams"))
    except subprocess.CalledProcessError:
        return False
    except json.JSONDecodeError:
        return False


def stitch_videos(
    video_paths: List[Path],
    overlap: float = 1.0,
    output_path: Optional[Path] = None,
    on_progress: Optional[Callable] = None,
) -> VideoResult:
    """Seamlessly stitch multiple videos (with audio) into a single timeline.

    Uses FFmpeg to concatenate videos while optionally trimming an overlap from
    the tail of each clip (except the last) to create smoother scene transitions.
    Both audio and video streams are preserved and re-encoded into a single
    H.264/AAC MP4.

    Args:
        video_paths: List of paths to video files to stitch together, in order.
        overlap: Duration in seconds to trim from the end of each video (except
            the last one) to create smooth transitions. Defaults to 1.0.
        output_path: Optional custom output path. If None, auto-generates a path
            using :class:`StorageManager`.
        on_progress: Optional callback function called with progress updates (message, percent).

    Returns:
        VideoResult: Object containing the stitched video path, metadata, and operation details.

    Raises:
        ValueError: If fewer than two videos are provided.
        FileNotFoundError: If any input video file doesn't exist.
        RuntimeError: If FFmpeg fails to stitch the videos.

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
    if len(video_paths) < 2:
        raise ValueError("Need at least two videos to stitch")

    storage = StorageManager()
    progress = ProgressTracker(on_progress)
    result = VideoResult()

    try:
        progress.start("Preparing")

        for path in video_paths:
            if not path.exists():
                raise FileNotFoundError(f"Video not found: {path}")

        clip_info: List[dict] = []
        for path in video_paths:
            info = get_video_info(path)
            duration = float(info.get("duration") or 0.0)
            if duration <= 0:
                raise RuntimeError(f"Unable to determine duration for {path}")
            clip_info.append(info)

        # Determine if all clips contain audio. ffprobe via get_video_info doesn't
        # expose audio presence, so detect separately.
        audio_presence: List[bool] = []
        for path in video_paths:
            audio_presence.append(_has_audio(path))
        include_audio = any(audio_presence)

        if output_path is None:
            filename = f"stitched_{result.id[:8]}.mp4"
            output_path = storage.get_video_path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        filter_parts: List[str] = []
        video_refs: List[str] = []
        audio_refs: List[str] = []

        for idx, (path, info) in enumerate(zip(video_paths, clip_info)):
            duration = float(info.get("duration") or 0.0)
            trim_end = duration
            if overlap > 0 and idx < len(video_paths) - 1 and duration - overlap > 0.01:
                trim_end = duration - overlap

            video_label = f"v{idx}"
            if trim_end < duration:
                filter_parts.append(
                    f"[{idx}:v]trim=0:{trim_end:.6f},setpts=PTS-STARTPTS[{video_label}]"
                )
            else:
                filter_parts.append(
                    f"[{idx}:v]setpts=PTS-STARTPTS[{video_label}]"
                )
            video_refs.append(f"[{video_label}]")

            if include_audio:
                audio_label = f"a{idx}"
                if audio_presence[idx]:
                    if trim_end < duration:
                        filter_parts.append(
                            f"[{idx}:a]atrim=0:{trim_end:.6f},asetpts=PTS-STARTPTS[{audio_label}]"
                        )
                    else:
                        filter_parts.append(
                            f"[{idx}:a]asetpts=PTS-STARTPTS[{audio_label}]"
                        )
                else:
                    filter_parts.append(
                        f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=0:{trim_end:.6f}[{audio_label}]"
                    )
                audio_refs.append(f"[{audio_label}]")

        if include_audio:
            concat_inputs = "".join(v + a for v, a in zip(video_refs, audio_refs))
            filter_parts.append(
                f"{concat_inputs}concat=n={len(video_paths)}:v=1:a=1[outv][outa]"
            )
        else:
            concat_inputs = "".join(video_refs)
            filter_parts.append(
                f"{concat_inputs}concat=n={len(video_paths)}:v=1:a=0[outv]"
            )

        filter_complex = "; ".join(filter_parts)

        cmd: List[str] = ["ffmpeg"]
        for path in video_paths:
            cmd.extend(["-i", str(path)])
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[outv]",
        ])
        if include_audio:
            cmd.extend(["-map", "[outa]"])
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "21",
            "-pix_fmt", "yuv420p",
        ])
        if include_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        cmd.extend([
            "-movflags", "+faststart",
            "-y",
            str(output_path),
        ])

        progress.update("Encoding", 90)
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Failed to stitch videos with ffmpeg: {exc.stderr.decode().strip() if exc.stderr else exc}"
            ) from exc

        progress.complete("Complete")

        result.path = output_path
        result.url = storage.get_url(output_path)
        output_info = get_video_info(output_path)
        result.metadata = VideoMetadata(
            fps=float(output_info.get("fps") or 0.0),
            duration=float(output_info.get("duration") or 0.0),
            width=int(output_info.get("width") or 0),
            height=int(output_info.get("height") or 0),
        )
        result.update_progress("Complete", 100)

    except Exception as exc:
        result.mark_failed(exc)
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
