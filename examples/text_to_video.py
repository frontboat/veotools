#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import veotools as veo

def generate_single_video(prompt: str, model: str | None = None):
    veo.init()
    
    print("Video Generation")
    print("=" * 50)
    print(f"Prompt: {prompt}")
    if not model:
        # Pick a sensible default from available models
        models = veo.list_models(include_remote=True)["models"]
        veo_models = [m for m in models if m["id"].startswith("veo-")]
        model = next((m["id"] for m in veo_models if "fast" in m["id"]), "veo-3.0-fast-generate-preview")
    print(f"Model: {model}")
    print("-" * 50)
    
    result = veo.generate_from_text(
        prompt,
        model=model,
        on_progress=lambda msg, pct: print(f"  {msg}: {pct}%")
    )
    
    print("\nGeneration complete")
    print(f"Path: {result.path}")
    print(f"Duration: {result.metadata.duration}s")
    print(f"FPS: {result.metadata.fps}")
    
    print("\nResult data:")
    data = result.to_dict()
    print(f"  ID: {data['id']}")
    print(f"  Status: {data['status']}")
    print(f"  Path: {data['path']}")
    
    return result

def main():
    default_prompt = "A majestic eagle soaring through mountain clouds at sunset"
    
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        print("Usage: python examples/text_to_video.py <your prompt> [model]")
        print(f"\nUsing default prompt: {default_prompt}")
        prompt = default_prompt
    model = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        result = generate_single_video(prompt, model)
        print(f"\nSuccess: {result.path}")
        print(f"URL: {result.url}")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()