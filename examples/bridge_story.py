#!/usr/bin/env python3
"""Build a short multi-scene story with the Bridge API."""

from __future__ import annotations

import argparse
import veotools as veo


def progress(message: str, percent: int) -> None:
    print(f"[{percent:3d}%] {message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge workflow example")
    parser.add_argument("--model", default="veo-3.1-generate-preview", help="Veo model to use")
    parser.add_argument("--overlap", type=float, default=1.0, help="Overlap trim when stitching")
    args = parser.parse_args()

    veo.init()

    bridge = veo.Bridge("mountain_story").with_progress(progress)
    bridge.generate("Sunrise over misty mountains, warm light flooding the valley", model=args.model)
    bridge.generate("A soaring eagle glides through the peaks", model=args.model)
    bridge.generate("The eagle lands as dusk settles over the range", model=args.model)

    final_result = bridge.stitch(overlap=args.overlap).save()
    print("Final stitched video:", final_result)


if __name__ == "__main__":
    main()
