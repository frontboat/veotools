# Veotools

Concise Python SDK and MCP server for generating and extending videos with Google Veo.

## Features
- Video generation from text, image seed, or continuation from an existing video
- Seamless extension workflow (extract last-second frame → generate → stitch with trim)
- MCP tools with progress streaming (start/get/cancel, continue_video) and recent videos resource
- Model discovery (local registry + remote list, cached)
- Accurate metadata via ffprobe/OpenCV; outputs under project `output/` (override with `VEO_OUTPUT_DIR`)

## Install

```bash
pip install veotools

# Or install from source
pip install -e .

pip install "veotools[mcp]"  # optional MCP CLI

# Set your API key
export GEMINI_API_KEY="your-api-key"
# Or create a .env file with:
# GEMINI_API_KEY=your-api-key
```

## SDK quick start

### Simple Video Generation

```python
import veotools as veo

# Initialize
veo.init()

# Generate video from text
result = veo.generate_from_text(
    "A serene mountain landscape at sunset",
    model="veo-3.0-fast-generate-preview"
)

print(f"Generated: {result.path}")
```

### Continue and stitch

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

## CLI

Install exposes the `veo` command. Use `-h/--help` on any subcommand.

```bash
# Basics
veo preflight
veo list-models --remote

# Generate from text
veo generate --prompt "cat riding a hat" --model veo-3.0-fast-generate-preview

# Continue a video and stitch seamlessly
veo continue --video dog.mp4 --prompt "the dog finds a treasure chest" --overlap 1.0

# Help
veo --help
veo generate --help
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

## Core functions

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

## MCP tools

These functions are designed for integration with MCP servers and return deterministic JSON-friendly dicts.

### System

```python
import veotools as veo

veo.preflight()
# -> { ok: bool, gemini_api_key: bool, ffmpeg: {installed, version}, write_permissions: bool, base_path: str }

veo.version()
# -> { veotools: str | None, dependencies: {...}, ffmpeg: str | None }
```

### Non-blocking generation jobs

```python
import veotools as veo

# Start a job immediately
start = veo.generate_start({
  "prompt": "A serene mountain landscape at sunset",
  "model": "veo-3.0-fast-generate-preview"
})
job_id = start["job_id"]

# Poll status
status = veo.generate_get(job_id)
# -> { job_id, status, progress, message, kind, remote_operation_id?, result?, error_code?, error_message? }

# Request cancellation (cooperative)
veo.generate_cancel(job_id)
```

## Model discovery
```python
models = veotools.list_models(include_remote=True)
print([m["id"] for m in models["models"] if m["id"].startswith("veo-")])
```

## Progress Tracking

```python
def my_progress(message: str, percent: int):
    print(f"{message}: {percent}%")

result = veo.generate_from_text(
    "sunset over ocean",
    on_progress=my_progress
)
```

## Web-ready results

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

- `examples/text_to_video.py`
- `examples/video_to_video.py`
- `examples/chained_workflow.py`
- `examples/all_functions.py`

## Layout

```
.
├── __init__.py
├── bridge.py
├── core.py
├── generate
│   ├── __init__.py
│   └── video.py
├── mcp_api.py
├── models.py
├── process
│   ├── __init__.py
│   └── extractor.py
└── stitch
    ├── __init__.py
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

## Notes

- Generation usually takes 1–3 minutes
- Veo access may require allowlist

## License

MIT

## Contributing

Pull requests welcome!

## Support

For issues and questions, please use GitHub Issues.