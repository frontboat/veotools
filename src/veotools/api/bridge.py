from pathlib import Path
from typing import List, Optional, Union, Callable

from ..models import Workflow, VideoResult
from ..generate.video import generate_from_text, generate_from_image, generate_from_video
from ..stitch.seamless import stitch_videos
from ..core import StorageManager

class Bridge:
    """A fluent API bridge for chaining video generation and processing operations.

    The Bridge class provides a convenient, chainable interface for combining multiple
    video operations like generation, stitching, and media management. It maintains
    an internal workflow and media queue to track operations and intermediate results.

    Attributes:
        workflow: Workflow object tracking all operations performed.
        media_queue: List of media file paths in processing order.
        results: List of VideoResult objects from generation operations.
        storage: StorageManager instance for file operations.

    Examples:
        Basic text-to-video generation:
        >>> bridge = Bridge("my_project")
        >>> result = bridge.generate("A cat playing").save()

        Chain multiple generations and stitch:
        >>> bridge = (Bridge("movie_project")
        ...     .generate("Opening scene")
        ...     .generate("Middle scene")
        ...     .generate("Ending scene")
        ...     .stitch(overlap=1.0)
        ...     .save(Path("final_movie.mp4")))

        Image-to-video with continuation:
        >>> bridge = (Bridge()
        ...     .add_media("photo.jpg")
        ...     .generate("The person starts walking")
        ...     .generate("They walk into the distance")
        ...     .stitch())
    """

    def __init__(self, name: Optional[str] = None):
        self.workflow = Workflow(name)
        self.media_queue: List[Path] = []
        self.results: List[VideoResult] = []
        self.storage = StorageManager()
        self._on_progress: Optional[Callable] = None
    
    def with_progress(self, callback: Callable) -> 'Bridge':
        """Set a progress callback for all subsequent operations.

        Args:
            callback: Function called with progress updates (message: str, percent: int).

        Returns:
            Bridge: Self for method chaining.

        Examples:
            >>> def show_progress(msg, pct):
            ...     print(f"{msg}: {pct}%")
            >>> bridge = Bridge().with_progress(show_progress)
        """
        self._on_progress = callback
        return self
    
    def add_media(self, media: Union[str, Path, List[Union[str, Path]]]) -> 'Bridge':
        """Add media files to the processing queue.

        Adds one or more media files (images or videos) to the internal queue.
        These files can be used as inputs for subsequent generation operations.

        Args:
            media: Single media path, or list of media paths to add to the queue.

        Returns:
            Bridge: Self for method chaining.

        Examples:
            Add a single image:
            >>> bridge = Bridge().add_media("photo.jpg")

            Add multiple videos:
            >>> files = ["video1.mp4", "video2.mp4", "video3.mp4"]
            >>> bridge = Bridge().add_media(files)

            Chain with Path objects:
            >>> bridge = Bridge().add_media(Path("input.mp4"))
        """
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
        """Generate a video using text prompt and optional media input.

        Generates a video based on the prompt and the most recent media in the queue.
        The generation method is automatically selected based on the media type:
        - No media: text-to-video generation
        - Image media: image-to-video generation
        - Video media: video continuation generation

        Args:
            prompt: Text description for video generation.
            model: Veo model to use. Defaults to "veo-3.0-fast-generate-preview".
            **kwargs: Additional generation parameters including:
                - extract_at: Time offset for video continuation (float)
                - duration_seconds: Video duration (int)
                - person_generation: Person policy (str)
                - enhance: Whether to enhance prompt (bool)

        Returns:
            Bridge: Self for method chaining.

        Raises:
            RuntimeError: If video generation fails.

        Examples:
            Text-to-video generation:
            >>> bridge = Bridge().generate("A sunset over mountains")

            Image-to-video with existing media:
            >>> bridge = (Bridge()
            ...     .add_media("landscape.jpg")
            ...     .generate("Clouds moving across the sky"))

            Video continuation:
            >>> bridge = (Bridge()
            ...     .add_media("scene1.mp4")
            ...     .generate("The action continues", extract_at=-2.0))

            Custom model and parameters:
            >>> bridge = Bridge().generate(
            ...     "A dancing robot",
            ...     model="veo-2.0",
            ...     duration_seconds=10,
            ...     enhance=True
            ... )
        """
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
        """Generate a transition video between the last two media items.

        Creates a smooth transition video that bridges the gap between the two most
        recent media items in the queue. The transition is generated from a frame
        extracted near the end of the second-to-last video.

        Args:
            prompt: Description of the desired transition. If None, uses a default
                "smooth cinematic transition between scenes".
            model: Veo model to use. Defaults to "veo-3.0-fast-generate-preview".

        Returns:
            Bridge: Self for method chaining.

        Raises:
            ValueError: If fewer than 2 media items are in the queue.

        Examples:
            Generate default transition:
            >>> bridge = (Bridge()
            ...     .add_media(["scene1.mp4", "scene2.mp4"])
            ...     .generate_transition())

            Custom transition prompt:
            >>> bridge = (Bridge()
            ...     .generate("Day scene")
            ...     .generate("Night scene")
            ...     .generate_transition("Gradual sunset transition"))

        Note:
            The transition video is inserted between the last two media items,
            creating a sequence like: [media_a, transition, media_b, ...]
        """
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
        """Stitch all videos in the queue into a single continuous video.

        Combines all video files in the media queue into one seamless video.
        Non-video files (images) are automatically filtered out. The result
        replaces the entire media queue.

        Args:
            overlap: Duration in seconds to trim from the end of each video
                (except the last) for smooth transitions. Defaults to 1.0.

        Returns:
            Bridge: Self for method chaining.

        Raises:
            ValueError: If fewer than 2 videos are available for stitching.

        Examples:
            Stitch with default overlap:
            >>> bridge = (Bridge()
            ...     .generate("Scene 1")
            ...     .generate("Scene 2")
            ...     .generate("Scene 3")
            ...     .stitch())

            Stitch without overlap:
            >>> bridge = bridge.stitch(overlap=0.0)

            Stitch with longer transitions:
            >>> bridge = bridge.stitch(overlap=2.5)

        Note:
            After stitching, the media queue contains only the final stitched video.
        """
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
        """Save the final result to a specified path or return the current path.

        Saves the most recent media file in the queue to the specified output path,
        or returns the current path if no output path is provided.

        Args:
            output_path: Optional destination path. If provided, copies the current
                result to this location. If None, returns the current file path.

        Returns:
            Path: The path where the final result is located.

        Raises:
            ValueError: If no media is available to save.

        Examples:
            Save to custom location:
            >>> final_path = bridge.save("my_video.mp4")
            >>> print(f"Video saved to: {final_path}")

            Get current result path:
            >>> current_path = bridge.save()
            >>> print(f"Current result: {current_path}")

            Save with Path object:
            >>> output_dir = Path("outputs")
            >>> final_path = bridge.save(output_dir / "final_video.mp4")
        """
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
        """Get the workflow object containing all performed operations.

        Returns:
            Workflow: The workflow tracking all operations and their parameters.

        Examples:
            >>> bridge = Bridge("project").generate("A scene").stitch()
            >>> workflow = bridge.get_workflow()
            >>> print(workflow.name)
        """
        return self.workflow
    
    def to_dict(self) -> dict:
        """Convert the workflow to a dictionary representation.

        Returns:
            dict: Dictionary containing workflow steps and metadata.

        Examples:
            >>> bridge = Bridge("test").generate("Scene")
            >>> workflow_dict = bridge.to_dict()
            >>> print(workflow_dict.keys())
        """
        return self.workflow.to_dict()
    
    def clear(self) -> 'Bridge':
        """Clear the media queue, removing all queued media files.

        Returns:
            Bridge: Self for method chaining.

        Examples:
            >>> bridge = Bridge().add_media(["a.mp4", "b.mp4"]).clear()
            >>> # Media queue is now empty
        """
        self.media_queue.clear()
        return self