#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import veo_tools as veo

def generate_single_video(prompt: str, model: str = "veo-3.0-fast-generate-preview"):
    veo.init()
    
    print("Video Generation")
    print("=" * 50)
    print(f"Prompt: {prompt}")
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
        print("Usage: python simple_generation.py <your prompt>")
        print(f"\nUsing default prompt: {default_prompt}")
        prompt = default_prompt
    
    print("\nAvailable models:")
    print("1. veo-3.0-fast-generate-preview (1 min, with audio)")
    print("2. veo-3.0-generate-preview (2 min, with audio)")
    print("3. veo-2.0-generate-001 (3 min, no audio, more control)")
    
    model_choice = input("\nSelect model (1-3, default=1): ").strip() or "1"
    
    models = {
        "1": "veo-3.0-fast-generate-preview",
        "2": "veo-3.0-generate-preview",
        "3": "veo-2.0-generate-001"
    }
    
    model = models.get(model_choice, "veo-3.0-fast-generate-preview")
    
    try:
        result = generate_single_video(prompt, model)
        print(f"\nSuccess: {result.path}")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()