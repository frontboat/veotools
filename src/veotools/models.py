from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import uuid4
from enum import Enum

class JobStatus(Enum):
    """Enumeration of possible job statuses for video generation tasks.
    
    Attributes:
        PENDING: Job has been created but not yet started.
        PROCESSING: Job is currently being processed.
        COMPLETE: Job has finished successfully.
        FAILED: Job has failed with an error.
    """
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"

class VideoMetadata:
    """Metadata information for a video file.
    
    Attributes:
        fps: Frames per second of the video.
        duration: Duration of the video in seconds.
        width: Width of the video in pixels.
        height: Height of the video in pixels.
        frame_count: Total number of frames in the video.
    
    Examples:
        >>> metadata = VideoMetadata(fps=30.0, duration=10.0, width=1920, height=1080)
        >>> print(metadata.frame_count)  # 300
        >>> print(metadata.to_dict())
    """
    def __init__(self, fps: float = 24.0, duration: float = 0.0, 
                 width: int = 0, height: int = 0):
        """Initialize video metadata.
        
        Args:
            fps: Frames per second (default: 24.0).
            duration: Video duration in seconds (default: 0.0).
            width: Video width in pixels (default: 0).
            height: Video height in pixels (default: 0).
        """
        self.fps = fps
        self.duration = duration
        self.width = width
        self.height = height
        self.frame_count = int(fps * duration) if duration > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to a dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary containing all metadata fields.
        """
        return {
            "fps": self.fps,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "frame_count": self.frame_count
        }

class VideoResult:
    """Result object for video generation operations.
    
    This class encapsulates all information about a video generation task,
    including its status, progress, metadata, and any errors.
    
    Attributes:
        id: Unique identifier for this result.
        path: Path to the generated video file.
        url: URL to access the video (if available).
        operation_id: Google API operation ID for tracking.
        status: Current status of the generation job.
        progress: Progress percentage (0-100).
        metadata: Video metadata (fps, duration, resolution).
        prompt: Text prompt used for generation.
        model: Model used for generation.
        error: Error information if generation failed.
        created_at: Timestamp when the job was created.
        completed_at: Timestamp when the job completed.
    
    Examples:
        >>> result = VideoResult()
        >>> result.update_progress("Generating", 50)
        >>> print(result.status)  # JobStatus.PROCESSING
        >>> result.update_progress("Complete", 100)
        >>> print(result.status)  # JobStatus.COMPLETE
    """
    def __init__(self, path: Optional[Path] = None, operation_id: Optional[str] = None):
        """Initialize a video result.
        
        Args:
            path: Optional path to the video file.
            operation_id: Optional Google API operation ID.
        """
        self.id = str(uuid4())
        self.path = path
        self.url = None
        self.operation_id = operation_id
        self.status = JobStatus.PENDING
        self.progress = 0
        self.metadata = VideoMetadata()
        self.prompt = None
        self.model = None
        self.error = None
        self.created_at = datetime.now()
        self.completed_at = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a JSON-serializable dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the video result.
        """
        return {
            "id": self.id,
            "path": str(self.path) if self.path else None,
            "url": self.url,
            "operation_id": self.operation_id,
            "status": self.status.value,
            "progress": self.progress,
            "metadata": self.metadata.to_dict(),
            "prompt": self.prompt,
            "model": self.model,
            "error": str(self.error) if self.error else None,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
    
    def update_progress(self, message: str, percent: int):
        """Update the progress of the video generation.
        
        Automatically updates the status based on progress:
        - 0%: PENDING
        - 1-99%: PROCESSING
        - 100%: COMPLETE
        
        Args:
            message: Progress message (currently unused but kept for API compatibility).
            percent: Progress percentage (0-100).
        """
        self.progress = percent
        if percent >= 100:
            self.status = JobStatus.COMPLETE
            self.completed_at = datetime.now()
        elif percent > 0:
            self.status = JobStatus.PROCESSING
    
    def mark_failed(self, error: Exception):
        """Mark the job as failed with an error.
        
        Args:
            error: The exception that caused the failure.
        """
        self.status = JobStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()

class WorkflowStep:
    """Individual step in a video processing workflow.
    
    Attributes:
        id: Unique identifier for this step.
        action: Action to perform (e.g., "generate", "stitch").
        params: Parameters for the action.
        result: Result of executing this step.
        created_at: Timestamp when the step was created.
    """
    def __init__(self, action: str, params: Dict[str, Any]):
        """Initialize a workflow step.
        
        Args:
            action: The action to perform.
            params: Parameters for the action.
        """
        self.id = str(uuid4())
        self.action = action
        self.params = params
        self.result = None
        self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the step to a dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the workflow step.
        """
        return {
            "id": self.id,
            "action": self.action,
            "params": self.params,
            "result": self.result.to_dict() if self.result else None,
            "created_at": self.created_at.isoformat()
        }

class Workflow:
    """Container for a multi-step video processing workflow.
    
    Workflows allow chaining multiple operations like generation,
    stitching, and processing into a single managed flow.
    
    Attributes:
        id: Unique identifier for this workflow.
        name: Human-readable name for the workflow.
        steps: List of workflow steps to execute.
        current_step: Index of the currently executing step.
        created_at: Timestamp when the workflow was created.
        updated_at: Timestamp of the last update.
    
    Examples:
        >>> workflow = Workflow("my_video_project")
        >>> workflow.add_step("generate", {"prompt": "sunset"})
        >>> workflow.add_step("stitch", {"videos": ["a.mp4", "b.mp4"]})
        >>> print(len(workflow.steps))  # 2
    """
    def __init__(self, name: Optional[str] = None):
        """Initialize a workflow.
        
        Args:
            name: Optional name for the workflow. If not provided,
                 generates a timestamp-based name.
        """
        self.id = str(uuid4())
        self.name = name or f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.steps: List[WorkflowStep] = []
        self.current_step = 0
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def add_step(self, action: str, params: Dict[str, Any]) -> WorkflowStep:
        """Add a new step to the workflow.
        
        Args:
            action: The action to perform.
            params: Parameters for the action.
            
        Returns:
            WorkflowStep: The created workflow step.
        """
        step = WorkflowStep(action, params)
        self.steps.append(step)
        self.updated_at = datetime.now()
        return step
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the workflow to a dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the workflow.
        """
        return {
            "id": self.id,
            "name": self.name,
            "steps": [step.to_dict() for step in self.steps],
            "current_step": self.current_step,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Workflow':
        """Create a workflow from a dictionary.
        
        Args:
            data: Dictionary containing workflow data.
            
        Returns:
            Workflow: Reconstructed workflow instance.
            
        Examples:
            >>> data = {"id": "123", "name": "test", "current_step": 2}
            >>> workflow = Workflow.from_dict(data)
            >>> print(workflow.name)  # "test"
        """
        workflow = cls(name=data.get("name"))
        workflow.id = data["id"]
        workflow.current_step = data.get("current_step", 0)
        return workflow