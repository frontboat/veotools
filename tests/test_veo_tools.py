#!/usr/bin/env python3
from pathlib import Path
import veo_tools as veo

def test_basic_imports():
    print("Testing imports...")
    assert veo.VeoClient is not None
    assert veo.VideoResult is not None
    assert veo.Bridge is not None
    assert veo.generate_from_text is not None
    assert veo.extract_frame is not None
    assert veo.stitch_videos is not None
    print("All imports successful")

def test_simple_generation():
    print("\nTest 1: Simple text generation")
    print("-" * 40)
    veo.init()
    def progress_callback(msg, pct):
        print(f"  {msg}: {pct}%")
    result = veo.generate_from_text(
        "A serene mountain landscape at sunset",
        model="veo-3.0-fast-generate-preview",
        on_progress=progress_callback
    )
    print(f"Generated video: {result.path}")
    print(f"Status: {result.status.value}")
    print(f"Result JSON: {result.to_dict()}")
    return result

def test_video_continuation():
    print("\nTest 2: Video continuation")
    print("-" * 40)
    test_video = Path("output/videos").glob("*.mp4")
    test_video = next(test_video, None)
    if not test_video:
        print("No test video found. Generate one first with test_simple_generation()")
        return
    print(f"Using video: {test_video}")
    result = veo.generate_from_video(
        test_video,
        "the scene transforms into a magical fantasy world",
        extract_at=-1.0,
        on_progress=lambda msg, pct: print(f"  {msg}: {pct}%")
    )
    print(f"Generated continuation: {result.path}")
    return result

def test_bridge_workflow():
    print("\nTest 3: Bridge workflow")
    print("-" * 40)
    test_videos = list(Path("output/videos").glob("*.mp4"))
    if len(test_videos) < 2:
        print("Need at least 2 videos. Run test_simple_generation() twice first.")
        return
    print(f"Using {len(test_videos)} videos")
    bridge = veo.Bridge("test_workflow")
    result_path = (bridge
        .with_progress(lambda msg, pct: print(f"  {msg}: {pct}%"))
        .add_media(test_videos[0])
        .add_media(test_videos[1])
        .stitch(overlap=1.0)
        .save("output/videos/test_stitched.mp4")
    )
    print(f"Workflow complete: {result_path}")
    workflow = bridge.get_workflow()
    print(f"\nWorkflow steps:")
    for step in workflow.steps:
        print(f"  - {step.action}: {step.params}")
    return result_path

def test_extract_frame():
    print("\nTest 4: Frame extraction")
    print("-" * 40)
    test_video = Path("output/videos").glob("*.mp4")
    test_video = next(test_video, None)
    if not test_video:
        print("No test video found. Generate one first.")
        return
    print(f"Extracting frame from: {test_video}")
    frame = veo.extract_frame(test_video, -1.0)
    print(f"Extracted frame: {frame}")
    info = veo.get_video_info(test_video)
    print(f"Video info: {info}")
    return frame

def main():
    print("=" * 50)
    print("Veo Tools SDK Test Suite")
    print("=" * 50)
    try:
        test_basic_imports()
        frame = test_extract_frame()
        print("\n" + "=" * 50)
        print("All tests completed successfully!")
        print("=" * 50)
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()