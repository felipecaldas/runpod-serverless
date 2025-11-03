# RunPod Serverless Worker for ComfyUI

This project implements a custom RunPod serverless worker that forwards requests from the RunPod platform to a ComfyUI server. It provides the required RunPod API endpoints (`/run`, `/runsync`, `/health`) while leveraging ComfyUI's powerful workflow execution capabilities.

## Architecture

The solution consists of:

1. **Custom Handler** (`src/handler.py`) - Implements the RunPod serverless API specification
2. **Start Script** (`src/start.sh`) - Manages ComfyUI startup and handler initialization  
3. **Docker Configuration** (`Dockerfile.runpod.serverless.v3`) - Builds the complete container image
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
  -f .\Dockerfile.runpod.serverless.v3 `
  -t your-dockerhub-username/runpod-comfyui-serverless:1.0 `
  .
```

### 2. Test Locally (Optional)

```powershell
# Test with CPU only
docker run --rm -it `
  -e SERVE_API_LOCALLY=true `
  -p 3000:3000 `
  -v "${PWD}\test_input.json:/workspace/test_input.json" `
  your-dockerhub-username/runpod-comfyui-serverless:1.0
```

The API will be available at `http://localhost:3000` with endpoints:
- `POST /run` - Asynchronous job submission
- `POST /runsync` - Synchronous job submission  
- `GET /health` - Health check

### 3. Push to Docker Registry

```powershell
docker login
docker push your-dockerhub-username/runpod-comfyui-serverless:1.0
```

### 4. Deploy to RunPod

1. Go to RunPod Console → Serverless → Templates
2. Create new template with:
   - **Container Image**: `your-dockerhub-username/runpod-comfyui-serverless:1.0`
   - **Container Disk**: 100 GB
   - **GPU**: 16-24 GB VRAM recommended
   - **Environment Variables**: None required
3. Deploy the template as a serverless endpoint

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
| `SERVE_API_LOCALLY` | `false` | Enable local API testing mode |
| `COMFY_LOG_LEVEL` | `DEBUG` | ComfyUI logging level |
| `BUCKET_ENDPOINT_URL` | - | S3 endpoint for image uploads |

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

### Workflow JSON

Export your ComfyUI workflow using **Workflow → Export (API)** in the ComfyUI interface.

### Input Images

Include base64-encoded images in the request:

```json
{
  "input": {
    "workflow": { ... },
    "images": [
      {
        "name": "input_image.png",
        "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg..."
      }
    ]
  }
}
```

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

## Development

### Local Testing

1. Build the image
2. Run with `SERVE_API_LOCALLY=true`
3. Test endpoints at `http://localhost:3000`
4. View API docs at `http://localhost:3000/docs`

### Adding Custom Models/Nodes

Modify `Dockerfile.runpod.serverless.v3`:

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
│   ├── handler.py              # Main RunPod handler implementation
│   └── start.sh                # Startup script
├── Dockerfile.runpod.serverless.v3 # Docker build configuration
├── requirements.txt            # Python dependencies
├── test_input.json            # Example workflow for testing
└── README.md                  # This file
```

## License

This project extends the RunPod worker-comfyui base image. Please refer to the respective licenses of the underlying components.
