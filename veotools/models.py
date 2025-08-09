from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import uuid4
from enum import Enum

class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"

class VideoMetadata:
    def __init__(self, fps: float = 24.0, duration: float = 0.0, 
                 width: int = 0, height: int = 0):
        self.fps = fps
        self.duration = duration
        self.width = width
        self.height = height
        self.frame_count = int(fps * duration) if duration > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fps": self.fps,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "frame_count": self.frame_count
        }

class VideoResult:
    def __init__(self, path: Optional[Path] = None, operation_id: Optional[str] = None):
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
        self.progress = percent
        if percent >= 100:
            self.status = JobStatus.COMPLETE
            self.completed_at = datetime.now()
        elif percent > 0:
            self.status = JobStatus.PROCESSING
    
    def mark_failed(self, error: Exception):
        self.status = JobStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()

class WorkflowStep:
    def __init__(self, action: str, params: Dict[str, Any]):
        self.id = str(uuid4())
        self.action = action
        self.params = params
        self.result = None
        self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "params": self.params,
            "result": self.result.to_dict() if self.result else None,
            "created_at": self.created_at.isoformat()
        }

class Workflow:
    def __init__(self, name: Optional[str] = None):
        self.id = str(uuid4())
        self.name = name or f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.steps: List[WorkflowStep] = []
        self.current_step = 0
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def add_step(self, action: str, params: Dict[str, Any]) -> WorkflowStep:
        step = WorkflowStep(action, params)
        self.steps.append(step)
        self.updated_at = datetime.now()
        return step
    
    def to_dict(self) -> Dict[str, Any]:
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
        workflow = cls(name=data.get("name"))
        workflow.id = data["id"]
        workflow.current_step = data.get("current_step", 0)
        return workflow