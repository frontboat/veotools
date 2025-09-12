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
from typing import Any, Dict, Optional

import veotools as veo


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


