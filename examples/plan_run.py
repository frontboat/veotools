#!/usr/bin/env python3
"""End-to-end demo: idea -> plan -> rendered video."""

from __future__ import annotations

import argparse
from pathlib import Path
import veotools as veo


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan and render a multi-scene video")
    parser.add_argument("idea", help="High-level concept for the story")
    parser.add_argument("--scenes", type=int, default=4, help="Number of clips (default 4)")
    parser.add_argument("--plan-model", default="gemini-2.5-pro", help="Gemini model for planning")
    parser.add_argument("--execute-model", default="veo-3.1-generate-preview", help="Veo model for rendering")
    parser.add_argument("--save-plan", default="output-plans/example_plan.json", help="Path to save the storyboard JSON")
    parser.add_argument("--seed-last-frame", action="store_true", help="Use previous clip's final frame as the next seed image")
    args = parser.parse_args()

    veo.init()

    print("Planning scenes with Gemini …")
    plan = veo.generate_scene_plan(
        args.idea,
        number_of_scenes=args.scenes,
        model=args.plan_model,
        save_path=args.save_plan,
    )
    print(f"✓ Plan saved to {args.save_plan}")

    print("\nRendering Veo clips …")
    execution = veo.execute_scene_plan(
        plan,
        model=args.execute_model,
        auto_seed_last_frame=args.seed_last_frame,
    )

    for clip in execution.clip_results:
        print(f" - Clip: {clip.path}")

    if execution.final_result:
        print(f"\nFinal stitched video: {execution.final_result.path}")


if __name__ == "__main__":
    main()
