# Veo Model Capabilities

## Models

### veo-3.0-fast-generate-preview
- Speed: ~1 min
- Parameters: `number_of_videos` only
- Use: Quick iterations

### veo-3.0-generate-preview  
- Speed: ~1-2 min
- Parameters: `number_of_videos` only
- Use: Higher quality

### veo-2.0-generate-001
- Speed: ~2-3 min  
- Parameters: `number_of_videos`, `duration_seconds` (3-10s), `enhance_prompt`, `fps`
- Use: Full control

## Parameters

**duration_seconds**: Veo 2.0 only (3-10 seconds)

**enhance_prompt**: Veo 2.0 only, improves prompts automatically

**number_of_videos**: All models, generates variations

## Input Types

- Text-to-Video: All models
- Image-to-Video: All models (used for stitching)
- Video-to-Video: Vertex AI only

## Stitching Notes

- Extract frame 1 second before video end
- Use extracted frame as next segment's starting image
- Trim 1 second overlap when combining videos
- Veo 2.0 better for precise duration control