# Veo Tools SDK

A Python toolkit for AI-powered video generation and seamless stitching using Google's Veo models.

## Features

- 🎬 **Video Generation** - Generate videos from text, images, or existing videos
- 🔗 **Seamless Stitching** - Automatically stitch videos with smart overlap trimming  
- 🎨 **Video Continuation** - Continue any video with AI from its last frame
- 🌉 **Bridge Workflows** - Chain operations together in fluent workflows
- 📊 **Web-Ready** - JSON-serializable results for API integration
- 🔄 **Progress Tracking** - Real-time progress callbacks for long operations

## Installation

```bash
# Install dependencies
pip install google-genai opencv-python numpy python-dotenv

# Set your API key
export GEMINI_API_KEY="your-api-key"
# Or create a .env file with:
# GEMINI_API_KEY=your-api-key
```

## Quick Start

### Simple Video Generation

```python
import veo_tools as veo

# Initialize
veo.init()

# Generate video from text
result = veo.generate_from_text(
    "A serene mountain landscape at sunset",
    model="veo-3.0-fast-generate-preview"
)

print(f"Generated: {result.path}")
```

### Continue Your Video

```python
# Continue from an existing video (like one from your phone)
result = veo.generate_from_video(
    "my_dog.mp4",
    "the dog discovers a treasure chest",
    extract_at=-1.0  # Use last frame
)

# Stitch them together seamlessly
final = veo.stitch_videos(
    ["my_dog.mp4", result.path],
    overlap=1.0  # Trim 1 second overlap
)
```

### Create a Story with Bridge

```python
# Chain operations together
bridge = veo.Bridge("my_story")

final_video = (bridge
    .add_media("sunrise.jpg")
    .generate("sunrise coming to life")
    .add_media("my_video.mp4")
    .generate("continuing the adventure")
    .stitch(overlap=1.0)
    .save("my_story.mp4")
)
```

## Core Functions

### Generation

- `generate_from_text(prompt, model, **kwargs)` - Generate video from text
- `generate_from_image(image_path, prompt, model, **kwargs)` - Generate video from image
- `generate_from_video(video_path, prompt, extract_at, model, **kwargs)` - Continue video

### Processing

- `extract_frame(video_path, time_offset)` - Extract single frame
- `extract_frames(video_path, times)` - Extract multiple frames
- `get_video_info(video_path)` - Get video metadata

### Stitching

- `stitch_videos(video_paths, overlap)` - Stitch videos with overlap trimming
- `stitch_with_transitions(videos, transitions)` - Stitch with transition videos

### Workflow

- `Bridge()` - Create workflow chains
- `VideoResult` - Web-ready result objects
- `ProgressTracker` - Progress callback handling

## Models

### Veo 3.0 Fast (Preview)
- **Model**: `veo-3.0-fast-generate-preview`
- **Speed**: ~1 minute
- **Audio**: Yes (native)
- **Duration**: 8 seconds

### Veo 3.0 (Preview)  
- **Model**: `veo-3.0-generate-preview`
- **Speed**: ~2 minutes
- **Audio**: Yes (native)
- **Duration**: 8 seconds

### Veo 2.0
- **Model**: `veo-2.0-generate-001`
- **Speed**: ~3 minutes
- **Audio**: No
- **Duration**: 3-10 seconds (configurable)
- **Extra**: Supports `enhance_prompt`, `fps` parameters

## Progress Tracking

```python
def my_progress(message: str, percent: int):
    print(f"{message}: {percent}%")

result = veo.generate_from_text(
    "sunset over ocean",
    on_progress=my_progress
)
```

## Web-Ready Results

All results are JSON-serializable for API integration:

```python
result = veo.generate_from_text("sunset")

# Convert to dictionary
data = result.to_dict()

# Ready for JSON API
import json
json_response = json.dumps(data)
```

## Examples

See the `examples/` folder for complete examples:

- `continue_video.py` - Continue any video with AI
- `create_story.py` - Create stories from mixed media
- `workflow_bridge.py` - Complex workflow examples

## Architecture

```
veo_tools/
├── core.py          # Client and configuration
├── models.py        # Data models (VideoResult, etc.)
├── bridge.py        # Workflow chaining
├── generate/        # Video generation
│   └── video.py
├── process/         # Video processing
│   └── extractor.py
└── stitch/          # Video stitching
    └── seamless.py
```

## Key Concepts

### VideoResult
Web-ready result object with metadata, progress, and JSON serialization.

### Bridge Pattern
Chain operations together for complex workflows:
```python
bridge.add_media().generate().stitch().save()
```

### Progress Callbacks
Track long-running operations:
```python
on_progress=lambda msg, pct: print(f"{msg}: {pct}%")
```

### Storage Manager
Organized file management (local now, cloud-ready for future).

## Limitations

- Video generation takes 1-3 minutes
- Veo access requires allowlist approval
- Generated videos are watermarked with SynthID
- Videos expire after 2 days on server

## Future Enhancements

- [ ] Gemini vision integration for smart transitions
- [ ] Batch processing for multiple videos
- [ ] FastAPI wrapper for REST API
- [ ] Cloud storage support (S3, GCS)
- [ ] Advanced transition effects

## License

MIT

## Contributing

Pull requests welcome! Please read CONTRIBUTING.md first.

## Support

For issues and questions, please use GitHub Issues.