# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python project for seamless video generation using Google's Veo models. Creates continuous video sequences by extracting frames from previous segments and using them as starting points for the next segment.

## Setup

```bash
# Environment
source venv/bin/activate
pip install -r requirements.txt

# Required: Create .env file with:
GEMINI_API_KEY=your_api_key

# Run
python veo_stitch.py
```

## Key Files

- `veo_stitch.py` - Main script for video generation and stitching
- `MODEL_CAPABILITIES.md` - Model specifications and parameters
- `requirements.txt` - Dependencies (google-genai, opencv-python, numpy, python-dotenv)

## Technical Details

### Available Models
- `veo-3.0-fast-generate-preview` - Fast, basic parameters
- `veo-3.0-generate-preview` - Higher quality, basic parameters  
- `veo-2.0-generate-001` - Full control (duration, enhance_prompt, fps)

### Stitching Workflow
1. Generate first video from text prompt
2. Extract frame 1 second before video end using OpenCV
3. Use extracted frame as input image for next video
4. Trim 1-second overlap when stitching to avoid duplication
5. Combine all segments into final video

### API Notes
- Video generation is async - requires polling
- Videos download using API key authentication
- Image objects require `location=` keyword argument
- Veo 3.0 models don't support duration_seconds or enhance_prompt
- Veo 2.0 supports all parameters

### Common Issues
- If video download fails, URI is saved to .txt file
- Frame extraction requires video to be fully downloaded
- Use consistent prompts for smooth transitions between segments