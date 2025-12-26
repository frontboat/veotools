#!/usr/bin/env python3
"""Minimal text-to-video generation example."""

from __future__ import annotations

import argparse
import veotools as veo


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Veo clip from text")
    parser.add_argument("prompt", help="Text prompt for the clip")
    parser.add_argument("--model", default="veo-3.1-generate-preview", help="Veo model to use")
    args = parser.parse_args()

    veo.init()

    print("Generating clip …")
    result = veo.generate_from_text(
        args.prompt,
        model=args.model,
        on_progress=lambda msg, pct: print(f"[{pct:3d}%] {msg}"),
    )

    print("\nClip saved:", result.path)
    print("Duration:", f"{result.metadata.duration:.1f}s")
    print("Resolution:", f"{result.metadata.width}x{result.metadata.height}")


if __name__ == "__main__":
    main()
