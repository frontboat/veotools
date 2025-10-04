"""Veotools command-line interface (no extra deps).

Usage examples:
  veo preflight
  veo list-models --remote
  veo generate --prompt "cat riding a hat" --model veo-3.0-fast-generate-preview
  veo continue --video dog.mp4 --prompt "the dog finds a treasure chest" --overlap 1.0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional, List

import veotools as veo


def _load_references(paths: Optional[List[str]]) -> Optional[List[Dict[str, Any]]]:
    """Load character reference JSON blobs from disk."""
    if not paths:
        return None
    refs: List[Dict[str, Any]] = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise FileNotFoundError(f"Reference file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            refs.extend(data)
        elif isinstance(data, dict):
            refs.append(data)
        else:
            raise ValueError(f"Reference file must contain JSON object/array: {path}")
    return refs


def _print_progress(message: str, percent: int):
    bar_length = 24
    filled = int(bar_length * percent / 100)
    bar = "#" * filled + "-" * (bar_length - filled)
    print(f"[{bar}] {percent:3d}% {message}", end="\r")
    if percent >= 100:
        print()


def cmd_preflight(_: argparse.Namespace) -> int:
    veo.init()
    data = veo.preflight()
    print(json.dumps(data, indent=2))
    return 0


def cmd_list_models(ns: argparse.Namespace) -> int:
    veo.init()
    data = veo.list_models(include_remote=ns.remote)
    if ns.json:
        print(json.dumps(data, indent=2))
    else:
        for m in data.get("models", []):
            print(m.get("id"))
    return 0


def cmd_generate(ns: argparse.Namespace) -> int:
    veo.init()
    kwargs: Dict[str, Any] = {}
    if ns.model:
        kwargs["model"] = ns.model
    if ns.aspect_ratio:
        kwargs["aspect_ratio"] = ns.aspect_ratio
    if ns.negative_prompt:
        kwargs["negative_prompt"] = ns.negative_prompt
    if ns.person_generation:
        kwargs["person_generation"] = ns.person_generation
    if ns.cached_content:
        kwargs["cached_content"] = ns.cached_content
    if ns.safety_json:
        try:
            parsed = json.loads(ns.safety_json)
            if isinstance(parsed, list):
                kwargs["safety_settings"] = parsed
        except Exception:
            pass
    if ns.image:
        result = veo.generate_from_image(
            image_path=Path(ns.image),
            prompt=ns.prompt,
            on_progress=_print_progress,
            **kwargs,
        )
    elif ns.video:
        result = veo.generate_from_video(
            video_path=Path(ns.video),
            prompt=ns.prompt,
            extract_at=ns.extract_at,
            on_progress=_print_progress,
            **kwargs,
        )
    else:
        result = veo.generate_from_text(
            ns.prompt,
            on_progress=_print_progress,
            **kwargs,
        )
    if ns.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.path)
    return 0


def cmd_plan(ns: argparse.Namespace) -> int:
    veo.init()

    references = _load_references(ns.reference)

    kwargs: Dict[str, Any] = {"number_of_scenes": ns.scenes}
    if ns.context:
        kwargs["additional_context"] = ns.context
    if ns.character_description:
        kwargs["character_description"] = ns.character_description
    if ns.character_traits:
        kwargs["character_characteristics"] = ns.character_traits
    if references:
        kwargs["character_references"] = references
    if ns.video_type:
        kwargs["video_type"] = ns.video_type
    if ns.video_characteristics:
        kwargs["video_characteristics"] = ns.video_characteristics
    if ns.camera_angle:
        kwargs["camera_angle"] = ns.camera_angle
    if ns.model:
        kwargs["model"] = ns.model
    if ns.save:
        kwargs["save_path"] = ns.save

    plan = veo.generate_scene_plan(ns.idea, **kwargs)

    if ns.json:
        print(plan.model_dump_json(indent=2))
    else:
        clip_ids = ", ".join(clip.id for clip in plan.clips)
        print(f"Generated plan with {len(plan.clips)} clip(s): {clip_ids}")
        if ns.save:
            print(f"Saved to {ns.save}")
    return 0


def cmd_plan_execute(ns: argparse.Namespace) -> int:
    veo.init()

    result = veo.execute_scene_plan(
        ns.plan,
        model=ns.model or "veo-3.0-generate-001",
        stitch=not ns.no_stitch,
        overlap=ns.overlap,
        auto_seed_last_frame=ns.seed_last_frame,
        seed_frame_offset=ns.seed_offset,
    )

    if ns.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"Rendered {len(result.clip_results)} clip(s)")
        for clip_result in result.clip_results:
            print(f" - {clip_result.path}")
        if result.final_result:
            print(f"Final video: {result.final_result.path}")
    return 0


def cmd_plan_run(ns: argparse.Namespace) -> int:
    veo.init()

    references = _load_references(ns.reference)

    plan_kwargs: Dict[str, Any] = {"number_of_scenes": ns.scenes}
    if ns.context:
        plan_kwargs["additional_context"] = ns.context
    if ns.character_description:
        plan_kwargs["character_description"] = ns.character_description
    if ns.character_traits:
        plan_kwargs["character_characteristics"] = ns.character_traits
    if references:
        plan_kwargs["character_references"] = references
    if ns.video_type:
        plan_kwargs["video_type"] = ns.video_type
    if ns.video_characteristics:
        plan_kwargs["video_characteristics"] = ns.video_characteristics
    if ns.camera_angle:
        plan_kwargs["camera_angle"] = ns.camera_angle
    if ns.plan_model:
        plan_kwargs["model"] = ns.plan_model
    if ns.save_plan:
        plan_kwargs["save_path"] = ns.save_plan

    plan = veo.generate_scene_plan(ns.idea, **plan_kwargs)

    exec_result = veo.execute_scene_plan(
        plan,
        model=ns.execute_model or "veo-3.0-generate-001",
        stitch=not ns.no_stitch,
        overlap=ns.overlap,
        auto_seed_last_frame=ns.seed_last_frame,
        seed_frame_offset=ns.seed_offset,
    )

    if ns.json:
        output = {
            "plan": json.loads(plan.model_dump_json()),
            "execution": exec_result.to_dict(),
        }
        print(json.dumps(output, indent=2))
    else:
        clip_ids = ", ".join(clip.id for clip in plan.clips)
        print(f"Generated plan with {len(plan.clips)} clip(s): {clip_ids}")
        print(f"Rendered {len(exec_result.clip_results)} clip(s)")
        for clip_result in exec_result.clip_results:
            print(f" - {clip_result.path}")
        if exec_result.final_result:
            print(f"Final video: {exec_result.final_result.path}")
        if ns.save_plan:
            print(f"Plan saved to {ns.save_plan}")
    return 0


def cmd_continue(ns: argparse.Namespace) -> int:
    veo.init()
    # Generate continuation
    kwargs: Dict[str, Any] = {}
    if ns.model:
        kwargs["model"] = ns.model
    if ns.aspect_ratio:
        kwargs["aspect_ratio"] = ns.aspect_ratio
    if ns.negative_prompt:
        kwargs["negative_prompt"] = ns.negative_prompt
    if ns.person_generation:
        kwargs["person_generation"] = ns.person_generation
    if ns.cached_content:
        kwargs["cached_content"] = ns.cached_content
    if ns.safety_json:
        try:
            parsed = json.loads(ns.safety_json)
            if isinstance(parsed, list):
                kwargs["safety_settings"] = parsed
        except Exception:
            pass
    gen = veo.generate_from_video(
        video_path=Path(ns.video),
        prompt=ns.prompt,
        extract_at=ns.extract_at,
        on_progress=_print_progress,
        **kwargs,
    )
    # Stitch with original
    stitched = veo.stitch_videos([Path(ns.video), Path(gen.path)], overlap=ns.overlap)
    if ns.json:
        out = {
            "generated": gen.to_dict(),
            "stitched": stitched.to_dict(),
        }
        print(json.dumps(out, indent=2))
    else:
        print(stitched.path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="veo", description="Veotools CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("preflight", help="Check environment and system prerequisites")
    s.set_defaults(func=cmd_preflight)

    s = sub.add_parser("list-models", help="List available models")
    s.add_argument("--remote", action="store_true", help="Include remote discovery")
    s.add_argument("--json", action="store_true", help="Output JSON")
    s.set_defaults(func=cmd_list_models)

    s = sub.add_parser("generate", help="Generate a video from text/image/video")
    s.add_argument("--prompt", required=True)
    s.add_argument("--model", help="Model ID (e.g., veo-3.0-fast-generate-preview)")
    s.add_argument("--image", help="Path to input image")
    s.add_argument("--video", help="Path to input video")
    s.add_argument("--extract-at", type=float, default=-1.0, help="Time offset for video continuation")
    s.add_argument("--aspect-ratio", choices=["16:9","9:16"], help="Requested aspect ratio (model-dependent)")
    s.add_argument("--negative-prompt", help="Text to avoid in generation")
    s.add_argument("--person-generation", choices=["allow_all","allow_adult","dont_allow"], help="Person generation policy (model/region dependent)")
    s.add_argument("--cached-content", help="Cached content name (from caching API)")
    s.add_argument("--safety-json", help="JSON list of {category, threshold} safety settings")
    s.add_argument("--json", action="store_true", help="Output JSON")
    s.set_defaults(func=cmd_generate)

    s = sub.add_parser("plan", help="Generate a structured scene plan using Gemini")
    s.add_argument("--idea", required=True, help="High-level concept for the plan")
    s.add_argument("--scenes", type=int, default=4, help="Number of scenes to generate (default 4)")
    s.add_argument("--character-description", help="Baseline description of the main character")
    s.add_argument("--character-traits", help="Personality traits of the character")
    s.add_argument("--context", help="Additional instructions or style notes")
    s.add_argument(
        "--reference",
        action="append",
        help="Path to JSON file containing character reference object/array (repeatable)",
    )
    s.add_argument("--video-type", help="Video type label")
    s.add_argument(
        "--video-characteristics",
        help="Overall stylistic notes",
    )
    s.add_argument(
        "--camera-angle",
        help="Primary camera perspective guidance",
    )
    s.add_argument("--model", help="Gemini model to use (default gemini-2.5-pro)")
    s.add_argument("--save", help="Path to save the raw JSON plan")
    s.add_argument("--json", action="store_true", help="Output JSON to stdout")
    s.set_defaults(func=cmd_plan)

    s = sub.add_parser("plan-execute", help="Render videos from a saved scene plan")
    s.add_argument("--plan", required=True, help="Path to the scene plan JSON file")
    s.add_argument("--model", help="Veo model to use for generation")
    s.add_argument("--overlap", type=float, default=1.0, help="Overlap trim (seconds) when stitching")
    s.add_argument("--no-stitch", action="store_true", help="Skip stitching clips into a final video")
    s.add_argument("--seed-last-frame", action="store_true", help="Use the previous clip's last frame as a seed image")
    s.add_argument("--seed-offset", type=float, default=-0.5, help="Time offset (seconds) for seed frame extraction (default -0.5)")
    s.add_argument("--json", action="store_true", help="Output JSON summary")
    s.set_defaults(func=cmd_plan_execute)

    s = sub.add_parser("plan-run", help="Plan and immediately execute the rendered video workflow")
    s.add_argument("--idea", required=True, help="High-level concept for the plan")
    s.add_argument("--scenes", type=int, default=4, help="Number of scenes to generate (default 4)")
    s.add_argument("--character-description", help="Baseline description of the main character")
    s.add_argument("--character-traits", help="Personality traits of the character")
    s.add_argument("--context", help="Additional instructions or style notes")
    s.add_argument(
        "--reference",
        action="append",
        help="Path to JSON file containing character reference object/array (repeatable)",
    )
    s.add_argument("--video-type", help="Video type label")
    s.add_argument(
        "--video-characteristics",
        help="Overall stylistic notes",
    )
    s.add_argument(
        "--camera-angle",
        help="Primary camera perspective guidance",
    )
    s.add_argument("--plan-model", help="Gemini model to use for planning (default gemini-2.5-pro)")
    s.add_argument("--save-plan", help="Optional path to save the generated plan JSON")
    s.add_argument("--execute-model", help="Veo model to use for rendering clips")
    s.add_argument("--overlap", type=float, default=1.0, help="Overlap trim (seconds) when stitching")
    s.add_argument("--no-stitch", action="store_true", help="Skip stitching clips into a final video")
    s.add_argument("--seed-last-frame", action="store_true", help="Use the previous clip's last frame as a seed image")
    s.add_argument("--seed-offset", type=float, default=-0.5, help="Time offset (seconds) for seed frame extraction (default -0.5)")
    s.add_argument("--json", action="store_true", help="Output JSON summary including plan and execution details")
    s.set_defaults(func=cmd_plan_run)

    s = sub.add_parser("continue", help="Continue a video and stitch seamlessly")
    s.add_argument("--video", required=True, help="Source video path")
    s.add_argument("--prompt", required=True)
    s.add_argument("--model", help="Model ID")
    s.add_argument("--extract-at", type=float, default=-1.0)
    s.add_argument("--overlap", type=float, default=1.0)
    s.add_argument("--aspect-ratio", choices=["16:9","9:16"], help="Requested aspect ratio (model-dependent)")
    s.add_argument("--negative-prompt", help="Text to avoid in generation")
    s.add_argument("--person-generation", choices=["allow_all","allow_adult","dont_allow"], help="Person generation policy (model/region dependent)")
    s.add_argument("--cached-content", help="Cached content name (from caching API)")
    s.add_argument("--safety-json", help="JSON list of {category, threshold} safety settings")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_continue)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
