"""Scene planning helpers powered by Gemini."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from google.genai import types
from pydantic import AnyUrl, BaseModel, Field

from ..core import VeoClient


class Shot(BaseModel):
    """Technical camera details for a specific clip."""

    composition: str = Field(..., description="How the shot is framed and the lens used.")
    camera_motion: Optional[str] = Field(
        None, description="Describes the movement of the camera during the shot."
    )
    frame_rate: str = Field(
        "24 fps", description="Frames per second, defining the motion look (24fps is cinematic)."
    )
    film_grain: Optional[float] = Field(None, description="Adds a stylistic film grain effect.")
    camera: str = Field(
        ..., description="Camera lens, shot type, and equipment style for this clip."
    )


class Subject(BaseModel):
    """Describes the character's appearance and wardrobe within a specific clip."""

    description: str = Field(
        ..., description="A full, descriptive prompt of the character for this shot."
    )
    wardrobe: str = Field(
        ..., description="The specific outfit worn in this clip. Based on the character's default outfit."
    )


class Scene(BaseModel):
    """Describes the setting and environment of the clip."""

    location: str = Field(..., description="The physical place where the scene occurs.")
    time_of_day: str = Field(
        "mid-day", description="The time of day, which heavily influences lighting."
    )
    environment: str = Field(
        ..., description="Specific environmental details that reinforce the setting."
    )


class VisualDetails(BaseModel):
    """Actions and props within the clip."""

    action: str = Field(..., description="What the character is doing in the scene.")
    props: Optional[str] = Field(None, description="Objects shown or used during the clip.")


class Cinematography(BaseModel):
    """Lighting, tone, and colour direction for the clip."""

    lighting: str = Field(
        ..., description="Specific lighting direction for this shot (e.g., high-key, moody).")
    tone: str = Field(..., description="Emotional tone of the clip.")
    color_grade: str = Field(..., description="Colour grade/look for the clip.")


class AudioTrack(BaseModel):
    """Defines the sound elements specific to this clip."""

    lyrics: Optional[str] = Field(None, description="Lyrics to be lip-synced or heard.")
    emotion: Optional[str] = Field(None, description="Emotional tone of the vocal performance.")
    flow: Optional[str] = Field(None, description="Rhythm and cadence of the lyrical delivery.")
    wave_download_url: Optional[AnyUrl] = Field(
        None, description="URL to a pre-existing audio file for this clip (if available)."
    )
    youtube_reference: Optional[AnyUrl] = Field(
        None, description="Reference video for music or mood."
    )
    audio_base64: Optional[str] = Field(None, description="Base64 encoded audio data.")
    format: str = Field("wav", description="Desired audio format, e.g. wav or mp3.")
    sample_rate_hz: int = Field(48000, description="Audio sample rate in Hertz.")
    channels: int = Field(2, description="Number of audio channels (1=mono, 2=stereo, etc.).")
    style: Optional[str] = Field(None, description="Genre/tempo/musical notes for the track.")


class Dialogue(BaseModel):
    """Defines the spoken lines and how they are presented."""

    character: str = Field(..., description="The character who is speaking.")
    line: str = Field(..., description="The exact line of dialogue or lyrics.")
    subtitles: bool = Field(
        False, description="Whether subtitles should appear (Veotools defaults to False)."
    )


class Performance(BaseModel):
    """Controls for the character's animated performance in this clip."""

    mouth_shape_intensity: Optional[float] = Field(
        None, description="How exaggerated the mouth shapes should be (0=subtle, 1=exaggerated)."
    )
    eye_contact_ratio: Optional[float] = Field(
        None, description="Percentage of time the character looks into camera."
    )


class Clip(BaseModel):
    """Defines a single video segment or shot."""

    id: str = Field(..., description="Unique identifier for this clip.")
    shot: Shot
    subject: Subject
    scene: Scene
    visual_details: VisualDetails
    cinematography: Cinematography
    audio_track: AudioTrack
    dialogue: Dialogue
    performance: Performance
    duration_sec: int = Field(..., description="Duration of the clip in seconds.")
    aspect_ratio: str = Field(
        "16:9", description="Aspect ratio for the clip (e.g., '16:9', '9:16')."
    )


class CharacterProfile(BaseModel):
    """A detailed, consistent profile of the character's core attributes."""

    name: str = Field(..., description="Primary name of the character.")
    age: int = Field(..., description="Character's apparent age.")
    height: str = Field(..., description="Character height, optionally in multiple units.")
    build: str = Field(..., description="Body type and physique description.")
    skin_tone: str = Field(..., description="Skin tone description.")
    hair: str = Field(..., description="Hair colour, length, and style.")
    eyes: str = Field(..., description="Eye shape and colour details.")
    distinguishing_marks: Optional[str] = Field(
        None, description="Unique features like tattoos, scars, or piercings."
    )
    demeanour: str = Field(..., description="Typical personality and mood.")
    default_outfit: str = Field(..., description="Primary outfit for the character.")
    mouth_shape_intensity: float = Field(
        ..., description="Baseline mouth movement exaggeration (0=subtle, 1=exaggerated)."
    )
    eye_contact_ratio: float = Field(
        ..., description="Baseline percentage of time looking into camera."
    )


class ScenePlan(BaseModel):
    """Structured response containing characters and clips."""

    characters: List[CharacterProfile]
    clips: List[Clip]

    def model_dump_json(self, *args, **kwargs) -> str:  # type: ignore[override]
        """Provide JSON serialisation helper that matches BaseModel signature."""
        return super().model_dump_json(*args, **kwargs)


BASE_GUIDANCE = """You are a cinematic video prompt writer for Google Veo. Veo can transform text or images into rich, character-driven video scenes.

Generate exactly {number_of_scenes} concise scene prompts capturing an approximately eight second moment each. Every prompt must describe the action, setting, mood, wardrobe, cinematography, and audio cues clearly enough for Veo to render without additional context.

Core Inputs:
- Idea: {idea}
{optional_inputs}

Additional Guidance:
- Maintain character and location continuity across clips unless explicitly told otherwise.
- Use vivid, specific language that balances story beats with production detail.
- If dialogue is needed, format it as `[tone]: "spoken words"`.
- Vary shot types and movement so the finished sequence feels dynamic.
- Ensure each prompt is self-contained and references no external material.
{custom_guidance}

Return a valid JSON object that matches the supplied schema exactly.
"""


class SceneWriter:
    """High-level helper for generating structured scene plans."""

    def __init__(self, model: str = "gemini-2.5-pro"):
        self.model = model
        wrapper = VeoClient()
        self._provider = getattr(wrapper, "provider", "google")
        self._client = getattr(wrapper, "client", None)
        if self._client is None:
            raise RuntimeError("Failed to initialise provider client for scene writing")

    @staticmethod
    def _build_prompt_sections(
        *,
        character_description: Optional[str],
        character_characteristics: Optional[str],
        additional_context: Optional[str],
        character_references: Optional[Sequence[CharacterProfile | dict]],
        video_type: Optional[str],
        video_characteristics: Optional[str],
        camera_angle: Optional[str],
    ) -> tuple[str, str]:
        input_lines: List[str] = []
        guidance_lines: List[str] = []

        if character_description:
            input_lines.append(f"- Character Description: {character_description.strip()}")
        if character_characteristics:
            input_lines.append(
                f"- Character Personality: {character_characteristics.strip()}"
            )
        if video_type:
            input_lines.append(f"- Video Type: {video_type.strip()}")
        if video_characteristics:
            input_lines.append(
                f"- Target Style: {video_characteristics.strip()}"
            )
        if camera_angle:
            input_lines.append(
                f"- Primary Camera Perspective: {camera_angle.strip()}"
            )
            guidance_lines.append(
                f"- When describing coverage, respect the primary perspective "
                f"{camera_angle.strip()} while still varying shot sizes."
            )
        if character_references:
            data = [
                ref.model_dump() if isinstance(ref, BaseModel) else ref
                for ref in character_references
            ]
            input_lines.append(
                "- Character References:\n" + json.dumps(data, indent=2)
            )
        if additional_context:
            guidance_lines.append(
                f"- Additional instructions: {additional_context.strip()}"
            )

        optional_inputs = (
            "\n".join(input_lines)
            if input_lines
            else "- (no additional structured inputs provided)"
        )
        custom_guidance = (
            "\n" + "\n".join(guidance_lines)
            if guidance_lines
            else ""
        )
        return optional_inputs, custom_guidance

    def generate(
        self,
        idea: str,
        *,
        number_of_scenes: int = 4,
        additional_context: Optional[str] = None,
        character_description: Optional[str] = None,
        character_characteristics: Optional[str] = None,
        character_references: Optional[Sequence[CharacterProfile | dict]] = None,
        video_type: Optional[str] = None,
        video_characteristics: Optional[str] = None,
        camera_angle: Optional[str] = None,
        model: Optional[str] = None,
        config: Optional[types.GenerateContentConfig] = None,
        response_model: type[ScenePlan] = ScenePlan,
        save_path: Optional[Path | str] = None,
    ) -> ScenePlan:
        """Generate a structured scene plan from a high-level idea.

        Args:
            idea: Core concept for the story (plain text).
            number_of_scenes: Desired number of clips in the plan.
            additional_context: Optional instructions or style notes.
            character_description: Baseline description of the lead character.
            character_characteristics: Personality traits for the character.
            character_references: Optional list of reference profiles passed to Gemini.
            video_type: High-level type of production (e.g., "vlog", "commercial").
            video_characteristics: Overall stylistic notes (e.g., "realistic, 4k, cinematic").
            camera_angle: Primary camera/perspective guidance for the scenes.
            model: Override the Gemini model name.
            config: Custom GenerateContentConfig; if omitted a JSON schema config is used.
            response_model: Pydantic model describing the expected response payload.
            save_path: Optional file path for writing the raw JSON plan.

        Returns:
            ScenePlan: Parsed response from Gemini respecting the response_model schema.
        """

        optional_inputs, custom_guidance = self._build_prompt_sections(
            character_description=character_description,
            character_characteristics=character_characteristics,
            additional_context=additional_context,
            character_references=character_references,
            video_type=video_type,
            video_characteristics=video_characteristics,
            camera_angle=camera_angle,
        )

        prompt = BASE_GUIDANCE.format(
            idea=idea.strip(),
            number_of_scenes=number_of_scenes,
            optional_inputs=optional_inputs,
            custom_guidance=custom_guidance,
        )

        schema = response_model.model_json_schema()

        if self._provider == "daydreams":
            raw = self._generate_plan_daydreams(prompt, schema, model or self.model)
        else:
            request_config = config or types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=schema,
            )
            raw = self._generate_plan_google(prompt, request_config, model or self.model)

        if not raw:
            raise RuntimeError("Scene writer returned an empty response")

        plan = response_model.model_validate_json(raw)

        if save_path:
            path = Path(save_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

        return plan


    def _generate_plan_google(
        self,
        prompt: str,
        request_config: types.GenerateContentConfig,
        model: str,
    ) -> str:
        result = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=request_config,
        )
        return getattr(result, "text", None)

    def _generate_plan_daydreams(
        self,
        prompt: str,
        schema: Dict[str, object],
        model: str,
    ) -> str:
        target_model = self._normalize_chat_model(model)
        payload = {
            "model": target_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a cinematic video prompt writer for Google Veo. "
                        "Return only valid JSON that matches the provided schema."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "ScenePlan",
                    "schema": schema,
                },
            },
        }

        response = self._client.create_chat_completion(payload)
        choices = response.get("choices", [])
        if not choices:
            raise RuntimeError("Daydreams Router returned no choices for scene plan request")

        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))

        if not content or not isinstance(content, str):
            raise RuntimeError("Daydreams Router response did not include textual content")

        normalized = self._strip_code_fence(content)
        try:
            data = json.loads(normalized)
        except json.JSONDecodeError:
            return normalized

        if isinstance(data, dict) and "characters" not in data and data.get("video_prompts"):
            converted = self._coerce_video_prompts(data["video_prompts"])
            return json.dumps(converted)

        return normalized

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        raw = text.strip()
        if not raw.startswith("```"):
            return raw

        # Remove leading fence with optional language identifier
        fence_pattern = re.compile(r"^```[a-zA-Z0-9_-]*\n?(.*)```$", re.DOTALL)
        match = fence_pattern.match(raw)
        if match:
            return match.group(1).strip()

        lines = raw.splitlines()
        if not lines:
            return raw
        stripped = lines[1:]
        while stripped and stripped[-1].strip() == "```":
            stripped.pop()
        return "\n".join(stripped).strip()

    @staticmethod
    def _coerce_video_prompts(prompts: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        clips: List[Dict[str, Any]] = []
        for idx, prompt_data in enumerate(prompts or [], start=1):
            if not isinstance(prompt_data, dict):
                continue
            scene_prompt = str(
                prompt_data.get("scene_prompt")
                or prompt_data.get("prompt")
                or prompt_data.get("description")
                or "")
            if not scene_prompt:
                scene_prompt = "Describe the scene in detail."

            duration = int(prompt_data.get("duration_seconds") or 8)
            aspect = str(prompt_data.get("aspect_ratio") or "16:9")
            location = prompt_data.get("setting") or prompt_data.get("location") or "Stylized arena"

            clip = {
                "id": f"clip-{idx}",
                "shot": {
                    "composition": "Dynamic animation frame",
                    "camera": "Storyboard camera",
                    "camera_motion": prompt_data.get("camera_motion") or "Sweeping motion",
                    "frame_rate": "24 fps",
                    "film_grain": None,
                },
                "subject": {
                    "description": scene_prompt,
                    "wardrobe": "Refer to scene prompt",
                },
                "scene": {
                    "location": location,
                    "time_of_day": prompt_data.get("time_of_day") or "unspecified",
                    "environment": prompt_data.get("environment") or scene_prompt,
                },
                "visual_details": {
                    "action": prompt_data.get("action") or scene_prompt,
                    "props": prompt_data.get("props") or "Prompt-driven elements",
                },
                "cinematography": {
                    "lighting": prompt_data.get("lighting") or "Stylized lighting",
                    "tone": prompt_data.get("tone") or "Energetic",
                    "color_grade": prompt_data.get("color_grade") or "High-contrast",
                },
                "audio_track": {
                    "lyrics": prompt_data.get("dialogue"),
                    "emotion": prompt_data.get("emotion") or "dynamic",
                    "flow": prompt_data.get("flow") or "syncopated",
                    "audio_base64": None,
                    "wave_download_url": None,
                    "youtube_reference": None,
                    "format": "wav",
                    "sample_rate_hz": 48000,
                    "channels": 2,
                },
                "dialogue": {
                    "character": prompt_data.get("speaker") or "Narrator",
                    "line": prompt_data.get("dialogue") or scene_prompt,
                    "subtitles": False,
                },
                "performance": {
                    "mouth_shape_intensity": 0.5,
                    "eye_contact_ratio": 0.5,
                },
                "duration_sec": duration,
                "aspect_ratio": aspect,
            }
            clips.append(clip)

        return {"characters": [], "clips": clips or []}

    @staticmethod
    def _normalize_chat_model(model: str) -> str:
        aliases = {
            "gemini-pro": "google-vertex/gemini-2.5-pro",
            "gemini-2.5-pro": "google-vertex/gemini-2.5-pro",
            "gemini-2.5-flash": "google-vertex/gemini-2.5-flash",
            "gemini-2.5-flash-lite": "google-vertex/gemini-2.5-flash-lite",
        }
        key = model.strip()
        return aliases.get(key, key)


def generate_scene_plan(
    idea: str,
    *,
    number_of_scenes: int = 4,
    additional_context: Optional[str] = None,
    character_description: Optional[str] = None,
    character_characteristics: Optional[str] = None,
    character_references: Optional[Sequence[CharacterProfile | dict]] = None,
    video_type: Optional[str] = None,
    video_characteristics: Optional[str] = None,
    camera_angle: Optional[str] = None,
    model: str = "gemini-2.5-pro",
    save_path: Optional[Path | str] = None,
) -> ScenePlan:
    """Convenience wrapper around :class:`SceneWriter` for one-off calls."""

    writer = SceneWriter(model=model)
    return writer.generate(
        idea,
        number_of_scenes=number_of_scenes,
        additional_context=additional_context,
        character_description=character_description,
        character_characteristics=character_characteristics,
        character_references=character_references,
        video_type=video_type,
        video_characteristics=video_characteristics,
        camera_angle=camera_angle,
        save_path=save_path,
    )


__all__ = [
    "ScenePlan",
    "CharacterProfile",
    "Clip",
    "SceneWriter",
    "generate_scene_plan",
]
