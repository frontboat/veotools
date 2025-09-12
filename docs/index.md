# Veotools Documentation

Welcome to the Veotools documentation! Veotools is a Python SDK and MCP server for generating and extending videos with Google Veo.

## Features

- 🎬 **Video Generation** - Generate videos from text prompts, images, or existing videos
- 🔗 **Seamless Stitching** - Combine videos with automatic overlap trimming
- 🤖 **MCP Integration** - Built-in Model Context Protocol server for AI assistants
- 📊 **Progress Tracking** - Real-time progress updates for long-running operations
- 💾 **Smart Caching** - Context caching for improved performance
- 🛡️ **Safety Controls** - Built-in safety settings pass-through

## Quick Example

```python
import veotools as veo

# Initialize the client
veo.init()

# Generate a video from text
result = veo.generate_from_text(
    "A serene mountain landscape at sunset",
    model="veo-3.0-fast-generate-preview"
)

print(f"Generated: {result.path}")
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