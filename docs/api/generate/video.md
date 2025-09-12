# Video Generation API

The video generation module provides functions for creating videos from various inputs using Google's Veo models.

## Functions

### generate_from_text

::: veotools.generate.video.generate_from_text

### generate_from_image

::: veotools.generate.video.generate_from_image

### generate_from_video

::: veotools.generate.video.generate_from_video

## Examples

### Text to Video

```python
import veotools as veo

veo.init()

# Basic generation
result = veo.generate_from_text(
    prompt="A cat playing piano",
    model="veo-3.0-fast-generate-preview"
)

# With progress tracking
def on_progress(message: str, percent: int):
    print(f"{message}: {percent}%")

result = veo.generate_from_text(
    prompt="Sunset over mountains",
    model="veo-3.0-fast-generate-preview",
    on_progress=on_progress
)
```

### Image to Video

```python
# Generate video from an image
result = veo.generate_from_image(
    image_path="landscape.jpg",
    prompt="The landscape comes to life with moving clouds",
    model="veo-3.0-fast-generate-preview"
)
```

### Video Continuation

```python
# Continue from existing video
result = veo.generate_from_video(
    video_path="intro.mp4",
    prompt="The scene transitions to a forest",
    extract_at=-1.0,  # Use last frame
    model="veo-3.0-fast-generate-preview"
)
```

## Model Support

Different Veo models support different features:

| Model | Duration Control | Aspect Ratio | Audio | Generation Time |
|-------|-----------------|--------------|-------|-----------------|
| veo-3.0-fast-generate-preview | ❌ | ✅ (16:9) | ✅ | ~1 min |
| veo-3.0-generate-preview | ❌ | ✅ (16:9) | ✅ | ~2 min |
| veo-2.0-generate-001 | ✅ | ✅ (16:9, 9:16) | ❌ | ~3 min |

## Safety Settings

You can pass safety settings to control content generation:

```python
from google.genai import types

safety_settings = [
    types.SafetySetting(
        category="HARM_CATEGORY_HARASSMENT",
        threshold="BLOCK_ONLY_HIGH"
    )
]

result = veo.generate_from_text(
    prompt="A friendly conversation",
    safety_settings=safety_settings
)
```