#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import veotools as veo

def example_1_simple_chain():
    print("Example 1: Simple Chain")
    print("-" * 40)
    
    bridge = veo.Bridge("simple_chain")
    
    result = (bridge
        .generate("A cat walking through a garden")
        .generate("The cat discovers a butterfly")
        .stitch(overlap=1.0)
        .save("output/videos/cat_story.mp4")
    )
    
    print(f"Result: {result}")

def example_2_mixed_media():
    print("\nExample 2: Mixed Media")
    print("-" * 40)
    
    bridge = veo.Bridge("mixed_media")
    
    result = (bridge
        .add_media("photo1.jpg")
        .generate("bring the photo to life with movement")
        .add_media("video1.mp4")
        .generate("continue the scene")
        .add_media("photo2.jpg")
        .generate("animate into final scene")
        .stitch(overlap=0.5)
        .save()
    )
    
    print(f"Result: {result}")

def example_3_with_progress():
    print("\nExample 3: Progress Tracking")
    print("-" * 40)
    
    def my_progress(message: str, percent: int):
        bar_length = 30
        filled = int(bar_length * percent / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"  [{bar}] {percent}% - {message}", end='\r')
        if percent >= 100:
            print()
    
    bridge = veo.Bridge("with_progress")
    
    result = (bridge
        .with_progress(my_progress)
        .generate("A time-lapse of clouds moving across the sky")
        .generate("The clouds form interesting shapes")
        .stitch()
        .save()
    )
    
    print(f"Result: {result}")

def example_4_transition_generation():
    print("\nExample 4: AI Transitions")
    print("-" * 40)
    
    bridge = veo.Bridge("transitions")
    
    result = (bridge
        .add_media("video1.mp4")
        .generate_transition("smooth morph between scenes")
        .add_media("video2.mp4")
        .stitch(overlap=0)
        .save()
    )
    
    print(f"Result: {result}")

def example_5_serializable_workflow():
    print("\nExample 5: Serializable Workflow")
    print("-" * 40)
    
    bridge = veo.Bridge("serializable")
    
    bridge.generate("First scene: sunrise over mountains")
    bridge.generate("Second scene: eagles flying")
    
    workflow_data = bridge.to_dict()
    
    print("Workflow structure:")
    print(f"  ID: {workflow_data['id']}")
    print(f"  Name: {workflow_data['name']}")
    print(f"  Steps: {len(workflow_data['steps'])}")
    
    for step in workflow_data['steps']:
        print(f"    - {step['action']}: {step['params'].get('prompt', 'N/A')[:30]}...")
    
    import json
    with open("output/workflow.json", "w") as f:
        json.dump(workflow_data, f, indent=2)
    
    print(f"\nWorkflow saved to output/workflow.json")

def main():
    print("=" * 50)
    print("Veo Tools - Bridge Pattern Examples")
    print("=" * 50)
    
    veo.init()
    
    example_1_simple_chain()
    example_3_with_progress()
    example_5_serializable_workflow()
    
    print("\n" + "=" * 50)
    print("Examples complete!")
    print("=" * 50)

if __name__ == "__main__":
    main()