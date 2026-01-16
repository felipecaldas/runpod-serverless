# Docker Commands for RunPod Serverless Worker

## Build the Docker Image

```powershell
# Build the image (no models included - much faster/smaller)
docker build --platform linux/amd64 -f Dockerfile.runpod.serverless -t runpod-comfyui-serverless:1.0 .
```

## Test the Container

### Option 1: Run Container Tests (Recommended)
```powershell
# Run comprehensive tests inside the container (CPU mode)
docker run --rm -e FORCE_CPU=true -e RUN_CONTAINER_TESTS=true runpod-comfyui-serverless:1.0
```

### Option 2: Interactive Shell
```powershell
# Get a shell inside the container for debugging
docker run --rm -it runpod-comfyui-serverless:1.0 bash
```

## Push to Registry (when ready)

```powershell
# Tag for your registry
docker tag runpod-comfyui-serverless:1.0 your-registry/runpod-comfyui-serverless:1.0

# Push to registry
docker push your-registry/runpod-comfyui-serverless:1.0
```

## Useful Commands

```powershell
# View image size
docker images runpod-comfyui-serverless:1.0

# View build logs
docker build --platform linux/amd64 -f Dockerfile.runpod.serverless -t runpod-comfyui-serverless:1.0 . --progress=plain

# Clean up if needed
docker rmi runpod-comfyui-serverless:1.0
```
