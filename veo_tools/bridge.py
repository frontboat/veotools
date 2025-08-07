from pathlib import Path
from typing import List, Optional, Union, Callable

from .models import Workflow, VideoResult
from .generate.video import generate_from_text, generate_from_image, generate_from_video
from .stitch.seamless import stitch_videos
from .core import StorageManager

class Bridge:
    def __init__(self, name: Optional[str] = None):
        self.workflow = Workflow(name)
        self.media_queue: List[Path] = []
        self.results: List[VideoResult] = []
        self.storage = StorageManager()
        self._on_progress: Optional[Callable] = None
    
    def with_progress(self, callback: Callable) -> 'Bridge':
        self._on_progress = callback
        return self
    
    def add_media(self, media: Union[str, Path, List[Union[str, Path]]]) -> 'Bridge':
        if isinstance(media, list):
            for m in media:
                self.media_queue.append(Path(m))
                self.workflow.add_step("add_media", {"path": str(m)})
        else:
            self.media_queue.append(Path(media))
            self.workflow.add_step("add_media", {"path": str(media)})
        return self
    
    def generate(self, prompt: str, model: str = "veo-3.0-fast-generate-preview", 
                 **kwargs) -> 'Bridge':
        step = self.workflow.add_step("generate", {
            "prompt": prompt,
            "model": model,
            **kwargs
        })
        
        if self.media_queue:
            last_media = self.media_queue[-1]
            
            if last_media.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                result = generate_from_image(
                    last_media,
                    prompt,
                    model=model,
                    on_progress=self._on_progress,
                    **kwargs
                )
            else:
                result = generate_from_video(
                    last_media,
                    prompt,
                    extract_at=kwargs.pop("extract_at", -1.0),
                    model=model,
                    on_progress=self._on_progress,
                    **kwargs
                )
        else:
            result = generate_from_text(
                prompt,
                model=model,
                on_progress=self._on_progress,
                **kwargs
            )
        
        step.result = result
        self.results.append(result)
        
        if result.path:
            self.media_queue.append(result.path)
        
        return self
    
    def generate_transition(self, prompt: Optional[str] = None, 
                           model: str = "veo-3.0-fast-generate-preview") -> 'Bridge':
        if len(self.media_queue) < 2:
            raise ValueError("Need at least 2 media items to create transition")
        
        media_a = self.media_queue[-2]
        media_b = self.media_queue[-1]
        
        if not prompt:
            prompt = "smooth cinematic transition between scenes"
        
        step = self.workflow.add_step("generate_transition", {
            "media_a": str(media_a),
            "media_b": str(media_b),
            "prompt": prompt,
            "model": model
        })
        
        result = generate_from_video(
            media_a,
            prompt,
            extract_at=-0.5,
            model=model,
            on_progress=self._on_progress
        )
        
        step.result = result
        self.results.append(result)
        
        if result.path:
            self.media_queue.insert(-1, result.path)
        
        return self
    
    def stitch(self, overlap: float = 1.0) -> 'Bridge':
        if len(self.media_queue) < 2:
            raise ValueError("Need at least 2 videos to stitch")
        
        video_paths = [
            p for p in self.media_queue 
            if p.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv']
        ]
        
        if len(video_paths) < 2:
            raise ValueError("Need at least 2 videos to stitch")
        
        step = self.workflow.add_step("stitch", {
            "videos": [str(p) for p in video_paths],
            "overlap": overlap
        })
        
        result = stitch_videos(
            video_paths,
            overlap=overlap,
            on_progress=self._on_progress
        )
        
        step.result = result
        self.results.append(result)
        
        if result.path:
            self.media_queue = [result.path]
        
        return self
    
    def save(self, output_path: Optional[Union[str, Path]] = None) -> Path:
        if not self.media_queue:
            raise ValueError("No media to save")
        
        last_media = self.media_queue[-1]
        
        if output_path:
            output_path = Path(output_path)
            import shutil
            shutil.copy2(last_media, output_path)
            return output_path
        
        return last_media
    
    def get_workflow(self) -> Workflow:
        return self.workflow
    
    def to_dict(self) -> dict:
        return self.workflow.to_dict()
    
    def clear(self) -> 'Bridge':
        self.media_queue.clear()
        return self