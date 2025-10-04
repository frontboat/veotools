# Veotools Documentation

Welcome to the Veotools documentation! Veotools is a Python SDK and MCP server for generating and extending videos with Google Veo.

## Features

- 🎬 **Video Generation** - Generate videos from text prompts, images, or existing videos
- 🔗 **Seamless Stitching** - Combine videos with automatic overlap trimming
- 🤖 **MCP Integration** - Built-in Model Context Protocol server for AI assistants
- 🧠 **Gemini Scene Planning** - Structured multi-clip story plans with character consistency
- 🛠️ **Plan Execution** - Render planned clips and stitch them into a finished video
- 📊 **Progress Tracking** - Real-time progress updates for long-running operations
- 💾 **Smart Caching** - Context caching for improved performance
- 🛡️ **Safety Controls** - Built-in safety settings pass-through

## Quick Start

```bash
veo plan-run --idea "Retro travel vlog" --execute-model veo-3.0-generate-001 --seed-last-frame
```

```python
import veotools as veo

veo.init()

plan = veo.generate_scene_plan("Retro travel vlog", number_of_scenes=4)
result = veo.execute_scene_plan(plan, model="veo-3.0-generate-001", auto_seed_last_frame=True)

print("Final video:", result.final_result.path if result.final_result else "clips only")
```

## Installation

```bash
# Basic installation
pip install veotools

# With MCP server support
pip install "veotools[mcp]"

# For development
pip install -e ".[dev,mcp,docs]"
```

## Navigation

- **[API Reference](api/overview.md)** - Complete API documentation with auto-generated docs from code

## Requirements

- Python 3.10+
- Google Gemini API key
- ffmpeg (for video processing)
- OpenCV (installed automatically)

## License

MIT License - see [LICENSE](https://github.com/frontboat/veotools/blob/main/LICENSE) for details.
