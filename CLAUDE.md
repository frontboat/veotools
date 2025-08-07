# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python project for generating seamless video sequences using Google's Veo3 model via the google-genai SDK. The goal is to create continuous videos by using the frame 1-second prior to the last frame of each video as input for generating the next video segment, then stitching them together.

## Development Setup

### Environment Configuration
- Requires Python virtual environment (venv)
- API key stored in `.env` file as `GEMINI_API_KEY`
- Uses google-genai SDK for accessing Veo3 model

### Key Dependencies
- `google-genai` - For accessing Google's generative AI models including Veo3
- Python 3.10+ recommended

### Common Commands

```bash
# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Install dependencies (when requirements.txt is created)
pip install -r requirements.txt

# Create requirements.txt from current environment
pip freeze > requirements.txt
```

## Architecture Overview

### Video Generation Workflow
1. Generate initial video using Veo3 with text/image prompt
2. Extract frame from 1 second before video end
3. Use extracted frame as input for next video generation
4. Repeat process to create video sequence
5. Stitch generated videos together for seamless output

### Key Technical Components

#### Veo3 Video Generation
- Model: `veo-2.0-generate-001`
- Supports text-to-video, image-to-video, and video-to-video generation
- Requires polling for operation completion (async generation)
- Configure duration, number of videos, and prompt enhancement

#### Client Configuration
```python
from google import genai
from google.genai import types

# Using Gemini Developer API with API key from .env
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
```

#### Video Generation Pattern
```python
# Create operation for video generation
operation = client.models.generate_videos(
    model='veo-2.0-generate-001',
    prompt='your prompt',
    config=types.GenerateVideosConfig(
        number_of_videos=1,
        duration_seconds=5,
        enhance_prompt=True,
    ),
)

# Poll until complete
while not operation.done:
    time.sleep(20)
    operation = client.operations.get(operation)

video = operation.response.generated_videos[0].video
```

## Implementation Notes

- Video generation is asynchronous - requires polling operation status
- Frame extraction for stitching should target 1 second before video end
- Consider using `last_frame` parameter in GenerateVideosConfig for frame interpolation
- Videos can be saved/loaded using the Video type's built-in methods
- For video-to-video generation on Vertex AI, input videos must be in Google Cloud Storage (gs:// URIs)