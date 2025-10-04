"""Execute scene plans into rendered videos."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from ..generate.video import generate_from_image, generate_from_text
from ..models import VideoResult
from ..stitch.seamless import stitch_videos
from ..process.extractor import extract_frame
from .scene_writer import ScenePlan, Clip


PromptBuilder = Callable[[Clip], str]
ImageProvider = Callable[[Clip, int, ScenePlan], Optional[Path]]
ClipOptionsProvider = Callable[[Clip, int, ScenePlan], Dict[str, object]]


@dataclass
class PlanExecutionResult:
    """Container for executing a :class:`ScenePlan`.

    Attributes:
        plan: The validated plan that was executed.
        clip_prompts: Prompts used for each clip in execution order.
        clip_results: Video results returned by Veo for each clip.
        final_result: The stitched video result, if stitching was requested.
    """

    plan: ScenePlan
    clip_prompts: List[str]
    clip_results: List[VideoResult]
    final_result: Optional[VideoResult]

    def to_dict(self) -> Dict[str, object]:
        """Convert execution details to a JSON-friendly dictionary."""

        return {
            "clips": [
                {
                    "prompt": prompt,
                    "result": result.to_dict(),
                }
                for prompt, result in zip(self.clip_prompts, self.clip_results)
            ],
            "final_result": self.final_result.to_dict() if self.final_result else None,
        }


def _load_plan_like(plan: ScenePlan | Path | str | Dict[str, object]) -> ScenePlan:
    if isinstance(plan, ScenePlan):
        return plan
    if isinstance(plan, (str, Path)):
        data = json.loads(Path(plan).read_text(encoding="utf-8"))
    elif isinstance(plan, dict):
        data = plan
    else:
        raise TypeError("plan must be ScenePlan, dict, or path to JSON file")
    return ScenePlan.model_validate(data)  # type: ignore[no-any-return]


def _default_prompt_builder(clip: Clip) -> str:
    lines: List[str] = [
        f"Clip ID: {clip.id}",
        f"Shot: {clip.shot.composition}",
    ]
    if clip.shot.camera:
        lines.append(f"Camera setup: {clip.shot.camera}")
    if clip.shot.camera_motion:
        lines.append(f"Camera motion: {clip.shot.camera_motion}")
    lines.append(f"Subject: {clip.subject.description}")
    lines.append(f"Wardrobe: {clip.subject.wardrobe}")
    lines.append(
        f"Environment: {clip.scene.location} during {clip.scene.time_of_day}"
    )
    if clip.scene.environment:
        lines.append(f"Setting details: {clip.scene.environment}")
    lines.append(f"Action: {clip.visual_details.action}")
    if clip.visual_details.props:
        lines.append(f"Props: {clip.visual_details.props}")
    lines.append(
        "Cinematography: "
        f"lighting {clip.cinematography.lighting}; tone {clip.cinematography.tone}; "
        f"grade {clip.cinematography.color_grade}"
    )
    lines.append(f"Aspect ratio: {clip.aspect_ratio}")
    if clip.dialogue.line:
        attribution = clip.dialogue.character or "Dialogue"
        lines.append(f"Dialogue: [{attribution}] {clip.dialogue.line}")
    audio_cues: List[str] = []
    if clip.audio_track.lyrics:
        audio_cues.append(f"lyrics '{clip.audio_track.lyrics}'")
    if clip.audio_track.emotion:
        audio_cues.append(f"emotion {clip.audio_track.emotion}")
    if clip.audio_track.flow:
        audio_cues.append(f"flow {clip.audio_track.flow}")
    if audio_cues:
        lines.append("Audio cues: " + "; ".join(audio_cues))
    lines.append("Render as a polished cinematic scene with synchronized audio.")
    return "\n".join(lines)


def execute_scene_plan(
    plan: ScenePlan | Path | str | Dict[str, object],
    *,
    model: str = "veo-3.0-generate-001",
    prompt_builder: Optional[PromptBuilder] = None,
    image_provider: Optional[ImageProvider] = None,
    clip_options: Optional[ClipOptionsProvider] = None,
    stitch: bool = True,
    overlap: float = 1.0,
    auto_seed_last_frame: bool = False,
    seed_frame_offset: float = -0.5,
    on_progress: Optional[Callable[[str, int], None]] = None,
) -> PlanExecutionResult:
    """Render all clips in a scene plan and optionally stitch the results.

    Args:
        plan: ScenePlan instance, dict payload, or path to plan JSON.
        model: Default Veo model to use for clip generation.
        prompt_builder: Optional callable to customize prompts per clip.
        image_provider: Optional callable returning a seed image path per clip.
        clip_options: Optional callable providing extra keyword args per clip.
        stitch: Whether to stitch the rendered clips into a final timeline.
        overlap: Overlap trimming in seconds when stitching.
        auto_seed_last_frame: When True, extract a frame from each rendered clip and
            feed it as the seed image for the next clip (unless an image_provider
            supplies one explicitly).
        seed_frame_offset: Time offset (seconds) used when extracting the frame
            from each clip for auto seeding. Defaults to -0.5 (half a second from end).
        on_progress: Optional progress callback used for generation and stitching.

    Returns:
        PlanExecutionResult containing individual clip results and optional final video.
    """

    scene_plan = _load_plan_like(plan)
    prompt_builder = prompt_builder or _default_prompt_builder
    clip_prompts: List[str] = []
    clip_results: List[VideoResult] = []

    total_clips = len(scene_plan.clips)

    last_seed_frame: Optional[Path] = None

    for idx, clip in enumerate(scene_plan.clips):
        prompt = prompt_builder(clip)
        clip_prompts.append(prompt)

        per_clip_kwargs = clip_options(clip, idx, scene_plan) if clip_options else {}
        per_clip_kwargs = dict(per_clip_kwargs or {})
        clip_model = per_clip_kwargs.pop("model", model)
        # Respect aspect ratio from the plan if not overridden.
        per_clip_kwargs.setdefault("aspect_ratio", clip.aspect_ratio)

        def _progress_wrapper(message: str, percent: int) -> None:
            if on_progress:
                on_progress(
                    f"Clip {idx + 1}/{total_clips}: {message}",
                    percent,
                )

        wrapped_progress = _progress_wrapper if on_progress else None

        image_path: Optional[Path] = None
        if image_provider:
            provided = image_provider(clip, idx, scene_plan)
            if provided:
                image_path = Path(provided)

        if image_path is None and auto_seed_last_frame and last_seed_frame:
            image_path = last_seed_frame

        if image_path:
            result = generate_from_image(
                image_path,
                prompt,
                model=clip_model,
                on_progress=wrapped_progress,
                **per_clip_kwargs,
            )
        else:
            result = generate_from_text(
                prompt,
                model=clip_model,
                on_progress=wrapped_progress,
                **per_clip_kwargs,
            )

        clip_results.append(result)

        if auto_seed_last_frame and result.path and idx < total_clips - 1:
            try:
                last_seed_frame = extract_frame(
                    result.path,
                    time_offset=seed_frame_offset,
                )
            except Exception:
                last_seed_frame = None

    clip_paths: List[Path] = [
        result.path for result in clip_results if result.path is not None
    ]

    final_result: Optional[VideoResult] = None
    if stitch and len(clip_paths) >= 2:

        def _stitch_progress(message: str, percent: int) -> None:
            if on_progress:
                on_progress(f"Stitching: {message}", percent)

        final_result = stitch_videos(
            clip_paths,
            overlap=overlap,
            on_progress=_stitch_progress if on_progress else None,
        )

    return PlanExecutionResult(
        plan=scene_plan,
        clip_prompts=clip_prompts,
        clip_results=clip_results,
        final_result=final_result,
    )


__all__ = ["PlanExecutionResult", "execute_scene_plan"]
