# RunPod Serverless Worker for ComfyUI

This project implements a custom RunPod serverless worker that forwards requests from the RunPod platform to a ComfyUI server. It provides the required RunPod API endpoints (`/run`, `/runsync`, `/health`) while leveraging ComfyUI's powerful workflow execution capabilities.

## Architecture

The solution consists of:

1. **Custom Handler** (`src/handler.py`) - Enhanced RunPod serverless API with validation and monitoring
2. **Start Script** (`src/start.sh`) - Production startup with symlinks to shared models  
3. **Docker Configuration** (`Dockerfile.runpod.serverless`) - Builds the complete container image
4. **Dependencies** (`requirements.txt`) - Python packages for the handler

## Key Features

- ✅ **RunPod API Compliance**: Implements `/run`, `/runsync`, and `/health` endpoints
- ✅ **Workflow Submission**: Accepts ComfyUI workflows in API format
- ✅ **Image Upload Support**: Handles base64-encoded input images
- ✅ **Real-time Monitoring**: Uses ComfyUI websocket API for job progress
- ✅ **Flexible Output**: Returns images as base64 or uploads to S3
- ✅ **Error Handling**: Comprehensive error reporting and logging
- ✅ **Custom Node Support**: Includes all necessary ComfyUI custom nodes

## Quick Start

### 1. Build the Docker Image

```powershell
cd y:\projects\runpod-serverless

docker build `
  -f .\Dockerfile.runpod.serverless `
  -t fcaldas/tabario.com:1.3 `
  .
```

### 2. Push to Docker Registry

```powershell
docker login
docker push fcaldas/tabario.com:1.3
```

### 3. Deploy to RunPod

1. Go to RunPod Console → Serverless → Templates
2. Create new template with:
   - **Container Image**: `fcaldas/tabario.com:1.3`
   - **Container Disk**: 100 GB
   - **GPU**: 16-24 GB VRAM recommended
   - **Environment Variables**:
     - `CIVITAI_API_KEY=<token>` when using Civitai-hosted models (only needed if you later enable runtime downloads)
3. Deploy the template as a serverless endpoint

## Models via Network Volume

This container uses a RunPod Network Volume mounted at `/runpod-volume`. On startup, it creates symlinks from `/runpod-volume/comfyui/models/<subfolder>` to `/comfyui/models/<subfolder>` so ComfyUI can load shared models without downloading.

Ensure your volume contains the expected ComfyUI subfolders and files, e.g. `vae`, `clip`, `unet`, `loras`, `checkpoints`, etc.

## API Usage

### Submit Workflow (Synchronous)

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d @test_input.json \
  https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync
```

### Submit Workflow (Asynchronous)

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d @test_input.json \
  https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run
```

### Response Format

```json
{
  "id": "sync-uuid-string",
  "status": "COMPLETED", 
  "output": {
    "images": [
      {
        "filename": "ComfyUI_00001_.png",
        "type": "base64",
        "data": "iVBORw0KGgoAAAANSUhEUg..."
      }
    ]
  },
  "delayTime": 123,
  "executionTime": 4567
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMFY_HOST` | `127.0.0.1:8188` | ComfyUI server address |
| `COMFY_LOG_LEVEL` | `DEBUG` | ComfyUI logging level |
| `BUCKET_ENDPOINT_URL` | - | S3 endpoint for image uploads |
| `CIVITAI_API_KEY` | - | Required to download Civitai-hosted models (e.g., `t2i-chroma-anime`) |

### S3 Configuration (Optional)

To enable S3 uploads instead of base64 responses:

```bash
# Set these environment variables in your RunPod template
BUCKET_ENDPOINT_URL=https://s3.amazonaws.com
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
BUCKET_NAME=your_bucket_name
```

## Input Format

The handler supports multiple ComfyUI workflow templates via the `comfyui_workflow_name` input.

### Workflow: Wan 2.2 Image-to-Video (I2V)

Use `comfyui_workflow_name: "video_wan2_2_14B_i2v"` (default). This workflow requires an input image and uses `width`, `height`, and `length`.

```json
{
  "input": {
    "prompt": "A beautiful sunset over the ocean with waves crashing",
    "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...",
    "width": 480,
    "height": 640,
    "length": 81,
    "comfyui_workflow_name": "video_wan2_2_14B_i2v"
  }
}
```

### Workflow: Qwen Text-to-Image (T2I)

Use `comfyui_workflow_name: "image_qwen_t2i"`. This workflow does **not** require `image`. The handler injects:

- `prompt` into `{{ IMAGE_PROMPT }}`
- `width` into `{{ IMAGE_WIDTH }}`
- `height` into `{{ IMAGE_HEIGHT }}`

as defined in `workflows/image_qwen_image_distill_official_comfyui.json` (notably the `EmptySD3LatentImage` node).

```json
{
  "input": {
    "prompt": "Slow cinematic push-in through the forest, 4K",
    "width": 720,
    "height": 1280,
    "comfyui_workflow_name": "image_qwen_t2i"
  }
}
```

### Required Fields
- **prompt** (string): Text prompt used by the selected workflow

### Optional Fields
- **image** (string): Base64-encoded input image (with or without data URI prefix). Required only for workflows that include `{{ INPUT_IMAGE }}` (e.g. Wan 2.2 I2V).
- **width** (int): Output width in pixels (default: 480)
- **height** (int): Output height in pixels (default: 640)
- **length** (int): Number of frames to generate (default: 81). Used by video workflows.
- **comfyui_workflow_name** (string): Workflow template key (default: `video_wan2_2_14B_i2v`). For Qwen T2I use `image_qwen_t2i`.

The handler will:
1. Load the selected workflow template (`comfyui_workflow_name`)
2. If the workflow contains `{{ INPUT_IMAGE }}`, upload the provided `image` to ComfyUI and inject the uploaded filename
3. Inject the prompt into the appropriate placeholder (e.g. `{{ VIDEO_PROMPT }}`, `{{ POSITIVE_PROMPT }}`, or `{{ IMAGE_PROMPT }}` depending on the workflow)
4. Inject `width`/`height` (and `length` for video workflows) into the workflow
5. Queue the workflow for processing

## Custom Nodes Included

- ComfyUI-GGUF (GGUF model support)
- ComfyUI-Frame-Interpolation (Video interpolation)
- ComfyUI-VideoHelperSuite (Video processing utilities)
- ComfyUI_ExtraModels (Additional model formats)
- ComfyUI-Unload-Model (Memory management)
- ComfyUI-Easy-Use (Utility nodes)

## Models Included

- **Stable Diffusion**: v1-5-pruned-emaonly-fp16.safetensors
- **Wan 2.2**: I2V models (High/Low noise GGUF)
- **VAEs**: wan_2.1_vae.safetensors, wan2.2_vae.safetensors, qwen_image_vae.safetensors
- **Text Encoders**: umt5-xxl-encoder-Q5_K_M.gguf, qwen_2.5_vl_7b_fp8_scaled.safetensors
- **LoRAs**: Wan2.2 Lightning LoRAs
- **Upscalers**: RealESRGAN_x2plus.pth
- **Frame Interpolation**: rife47.pth

### Adding Custom Models/Nodes

Modify `Dockerfile.runpod.serverless`:

```dockerfile
# Add custom nodes
RUN comfy-node-install https://github.com/your-repo/custom-node

# Download models
RUN wget -O models/checkpoints/your_model.safetensors https://url-to-model
```

## Troubleshooting

### Common Issues

1. **ComfyUI fails to start**
   - Check logs for model loading errors
   - Verify GPU memory is sufficient
   - Ensure all models downloaded successfully

2. **Handler not responding**
   - Verify ComfyUI is accessible: `curl http://127.0.0.1:8188/system_stats`
   - Check websocket connection: `ws://127.0.0.1:8188/ws`

3. **S3 upload failures**
   - Verify AWS credentials and permissions
   - Check bucket name and region
   - Ensure endpoint URL is correct

### Debug Mode

Enable detailed logging:

```bash
# Set environment variable
COMFY_LOG_LEVEL=DEBUG

# Or modify Dockerfile
ENV COMFY_LOG_LEVEL=DEBUG
```

## File Structure

```
runpod-serverless/
├── src/
│   ├── handler.py              # Enhanced RunPod handler with validation
│   └── start.sh                # Production startup script
├── Dockerfile.runpod.serverless # Docker build configuration
├── requirements.txt            # Python dependencies
├── test_input.json            # Example workflow for testing
├── save_base64_image.py        # Helper: decode base64 output image from JSON and save locally
└── README.md                  # This file
```

## License

This project extends the RunPod worker-comfyui base image. Please refer to the respective licenses of the underlying components.
