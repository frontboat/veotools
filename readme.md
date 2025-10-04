# Veotools

![PyPI - Downloads](https://img.shields.io/pypi/dm/veotools?style=flat-square&logo=python&labelColor=black&color=blue)

A Python toolkit for orchestrating multi-scene videos with Google Veo. Handles scene planning, video rendering, overlap-aware stitching, and progress tracking.

## Features
- **One-command stories** – Turn ideas into storyboards, render clips, and deliver stitched videos
- **Gemini planning** – Generate cinematic shot lists with consistent characters and dialogue
- **Veo rendering** – Full SDK access with Veo 3 defaults and customizable prompts
- **Audio-preserving stitching** – FFmpeg pipeline maintains perfect audio alignment
- **Python-first** – Clean API for programmatic video generation workflows

## Installation

```bash
pip install veotools # CLI and SDK
pip install "veotools[mcp]" # Add MCP server support
pip install -e ".[dev,mcp]" # Contribute / run tests locally

# Environment (choose your models / region access)
export GEMINI_API_KEY="your-gemini-key"

# Daydreams Router support (optional)
export VEO_PROVIDER="daydreams"
export DAYDREAMS_API_KEY="sk-router-..."
# export DAYDREAMS_BASE_URL="https://api-beta.daydreams.systems/v1" # override if needed
```

Set `VEO_PROVIDER=daydreams` to proxy prompts and video jobs through the Daydreams Router. Omit the flag (or set it to `google`) to call the Google GenAI SDK directly.

## Quick start (CLI)

```bash
# Plan + render + stitch in one command
veo plan-run \
  --idea "N64 Japanese retro explainer about the x402 protocol" \
  --save-plan output-plans/x402.json \
  --execute-model veo-3.0-generate-001 \
  --seed-last-frame --seed-offset -0.25
```

Outputs land under `output/`:
- `output-plans/x402.json` – Gemini storyboard (optional if you omit `--save-plan`).
- `output/videos/video_*.mp4` – Individual clips.
- `output/videos/stitched_*.mp4` – Final stitched master with audio.

You can also execute an existing plan:

```bash
veo plan-execute --plan output-plans/x402.json --model veo-3.0-generate-001 --seed-last-frame
```

…and generate only the storyboard:

```bash
veo plan --idea "Retro travel vlog" --scenes 4 --save output-plans/vlog.json --json
```

## Quick start (Python)

```python
import veotools as veo

veo.init()  # sets up logging + validates GEMINI_API_KEY

plan = veo.generate_scene_plan(
    "N64 Japanese retro explainer about the x402 protocol",
    number_of_scenes=4,
    additional_context="Keep the tone energetic and educational",
)

result = veo.execute_scene_plan(
    plan,
    model="veo-3.0-generate-001",
    auto_seed_last_frame=True,        # feed each clip the previous clip's final frame
    seed_frame_offset=-0.25,          # extract the seed frame 0.25s before the end
)

print("Rendered clip files:")
for clip in result.clip_results:
    print(" -", clip.path)

if result.final_result:
    print("Final stitched video:", result.final_result.path)
```

## CLI overview
- `veo plan` – Generate / save a Gemini storyboard (structured JSON).
- `veo plan-execute` – Render clips + stitch an existing plan.
- `veo plan-run` – Plan and execute in one shot (see quick start).
- `veo generate` / `veo continue` – Low-level Veo helpers for ad hoc clips.
- `veo list-models`, `veo preflight` – Environment + model diagnostics.

Run `veo <command> --help` for full flag descriptions.

## Python API map

| Task | Function(s) |
|------|-------------|
| Scene planning | `generate_scene_plan`, `SceneWriter` |
| Plan execution | `execute_scene_plan`, `PlanExecutionResult` |
| Single clip generation | `generate_from_text`, `generate_from_image`, `generate_from_video` |
| Media analysis | `extract_frame`, `extract_frames`, `get_video_info` |
| Stitching | `stitch_videos`, `stitch_with_transitions`, `create_transition_points` |
| Workflow chaining | `Bridge` (fluent API for multi-step stories) |

### Model / safety notes
- Veo 3 text-to-video clips default to `person_generation="allow_all"`; image/video-seeded clips default to `allow_adult`. Override via keyword arguments if you need a different policy.
- Use `list_models(include_remote=True)` to discover the Veo variants your account can access (stable IDs: `veo-3.0-generate-001`, `veo-3.0-fast-generate-001`, etc.).

### Storage layout
- `output/videos/` – All rendered clips, stitched deliverables, and intermediate assets.
- `output/frames/` – Extracted stills (including auto-seed frames when enabled).
- `output/ops/` – MCP job records, cached model lists, etc.
- Override with `VEO_OUTPUT_DIR` or pass a custom base path to `StorageManager`.

## Examples
- `examples/plan_run.py` – Full idea → plan → render workflow in ~30 lines.
- `examples/text_to_video.py` – Minimal text-to-video clip generator.
- `examples/bridge_story.py` – Build a three-scene story with the fluent `Bridge` API.

## Contributing & tests
Pull requests are welcome! Please:
1. Install with `pip install -e ".[dev,mcp]"`.
2. Run `pytest` (the suite relies on mocks; no live API calls).
3. Update docs/examples when behaviour changes.

MCP users can launch the server with `veo-mcp` or `python -m veotools.server.mcp_server`.
