# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Veotools is a Python SDK and MCP server for generating and extending videos with Google Veo. It provides:
- Video generation from text, image seed, or continuation from existing video
- Veo 3.1 helpers for reference images, interpolation, and video extension
- Seamless video stitching with overlap trimming
- MCP (Model Context Protocol) server integration for AI assistants
- Progress tracking and caching support

## Development Commands

### Setup
```bash
# Install in development mode with all dependencies
pip install -e ".[dev,mcp]"

# Install production only
pip install -e .
```

### Testing
```bash
# Run all tests
pytest

# Run specific test categories
pytest -m unit              # Fast unit tests only
pytest -m integration       # Integration tests
pytest -m "not slow"        # Skip slow tests

# Coverage
pytest --cov=veotools --cov-report=html

# Using Make commands
make test                   # Run all tests
make test-unit              # Run unit tests only
make test-coverage          # Generate coverage report
make test-parallel          # Run tests in parallel
```

### Build and Package
```bash
# Build distributions for PyPI
python -m build

# Clean build artifacts
make clean

# Check version consistency before release
python scripts/check_version.py
```

### Running the CLI
```bash
# Main CLI entry point
veo --help

# MCP server (when installed with [mcp])
veo-mcp
```

## Architecture

### Core Components

**VeoClient** (`src/veotools/core.py`): Singleton client managing Google GenAI API connection. Initialized with `GEMINI_API_KEY` from environment.

**StorageManager** (`src/veotools/core.py`): Manages output directories with resolution order:
1. `VEO_OUTPUT_DIR` environment variable
2. `./output` in current working directory
3. Package-adjacent directory as fallback

**VideoResult** (`src/veotools/models.py`): Web-ready result objects with metadata, JSON serialization, and progress tracking. All generation functions return these objects.

**Bridge** (`src/veotools/api/bridge.py`): Workflow orchestration for chaining operations (add_media → generate → stitch → save).

### Module Structure

```
src/veotools/
├── core.py          - Core client and storage management
├── models.py        - Data models and result objects
├── cli.py           - Command-line interface
├── api/
│   ├── bridge.py    - Workflow orchestration API
│   └── mcp_api.py   - MCP-friendly wrapper functions
├── generate/
│   └── video.py     - Video generation from text/image/video
├── process/
│   └── extractor.py - Frame extraction and video metadata
├── stitch/
│   └── seamless.py  - Video stitching with transitions
└── server/
    └── mcp_server.py - MCP server implementation
```

### Key Patterns

1. **Progress Tracking**: All long-running operations accept `on_progress` callbacks
2. **Async Job Management**: Non-blocking generation via `generate_start/get/cancel`
3. **Model Configuration**: Dynamic model discovery with local registry + remote listing
4. **Safety Settings**: Pass-through support for Google's safety configuration
5. **Context Caching**: Helper functions for creating and managing cached content

### Environment Variables

- `GEMINI_API_KEY`: Required for Google GenAI API access
- `VEO_OUTPUT_DIR`: Optional override for output directory location

### Model Constraints

Person generation varies by Veo model and mode:
- **Veo 3.1**: text/extension allows `allow_all`; image/interpolation/reference allows `allow_adult`
- **Veo 3.0**: text→video allows `allow_all`; image/video-seeded allows `allow_adult`
- **Veo 2.0**: text→video allows `allow_all`, `allow_adult`, `dont_allow`; image/video-seeded allows `allow_adult`, `dont_allow`

### Testing Conventions

**Test Organization**
- Tests mirror source structure in `tests/` directory
- Shared fixtures in `tests/conftest.py`
- Mock all external dependencies (API calls, ffmpeg)
- Use pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`

**Test Patterns**
- Follow AAA pattern (Arrange-Act-Assert)
- Name tests descriptively: `test_<what_is_being_tested>`
- Group related tests in classes: `TestClassName`
- Use parametrized tests for multiple scenarios
- Mock Google GenAI client to avoid real API calls

**Key Fixtures** (in `conftest.py`)
- `mock_api_key` - Auto-sets test API key
- `mock_veo_client` - Mocked VeoClient
- `temp_output_dir` - Temporary directory for test outputs
- `mock_video_file` - Fake video file for testing
- `mock_genai_response` - Mocked API responses

### Dependencies

Core dependencies managed in `pyproject.toml`:
- `google-genai>=1.56.0` - Google's generative AI client
- `opencv-python>=4.8.0` - Video processing
- `python-dotenv>=1.0.0` - Environment configuration
- `mcp[cli]>=1.25.0` (optional) - MCP server support

Development dependencies:
- `pytest>=7.4.0` - Testing framework
- `pytest-asyncio>=0.21.0` - Async test support
- `pytest-cov>=4.1.0` - Coverage reporting
- `pytest-mock>=3.11.0` - Mocking utilities
- `pytest-xdist>=3.3.0` - Parallel test execution
