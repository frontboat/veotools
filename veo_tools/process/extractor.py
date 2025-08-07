"""Frame extraction utilities for Veo Tools."""

import cv2
from pathlib import Path
from typing import Optional

from ..core import StorageManager


def extract_frame(
    video_path: Path,
    time_offset: float = -1.0,
    output_path: Optional[Path] = None
) -> Path:
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
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    
    cap = cv2.VideoCapture(str(video_path))
    
    try:
        info = {
            "fps": cap.get(cv2.CAP_PROP_FPS),
            "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        }
        
        info["duration"] = info["frame_count"] / info["fps"] if info["fps"] > 0 else 0
        
        return info
        
    finally:
        cap.release()