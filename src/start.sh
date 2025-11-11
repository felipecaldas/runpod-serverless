#!/bin/bash

# Production start script for RunPod serverless worker
# Based on official runpod/worker-comfyui:5.1.0-base with runtime model downloads

set -e

echo "Starting RunPod serverless worker (official base + optimizations)..."

# Set working directory
cd /comfyui

# Setup symlinks to models from RunPod network volume
echo "Setting up model symlinks..."

LOCAL_MODELS="/comfyui/models"
mkdir -p "$LOCAL_MODELS"

# Check both possible volume locations
if [ -d "/runpod-volume/comfyui/models" ]; then
    VOLUME_MODELS="/runpod-volume/comfyui/models"
elif [ -d "/workspace/comfyui/models" ]; then
    VOLUME_MODELS="/workspace/comfyui/models"
else
    VOLUME_MODELS=""
fi

if [ -n "$VOLUME_MODELS" ] && [ -d "$VOLUME_MODELS" ]; then
    echo "Linking model subfolders from $VOLUME_MODELS into $LOCAL_MODELS"
    for sub in vae clip checkpoints unet loras upscale_models text_encoders diffusion_models; do
        src="$VOLUME_MODELS/$sub"
        dst="$LOCAL_MODELS/$sub"
        if [ -d "$src" ]; then
            rm -rf "$dst"
            ln -s "$src" "$dst"
            echo "  -> $sub"
        fi
    done
else
    echo "Warning: No compatible network volume found at /runpod-volume or /workspace"
fi

echo "Starting ComfyUI server..."

# Check if we should run the local API server for testing
if [ "$SERVE_API_LOCALLY" = "true" ]; then
    echo "Starting ComfyUI with local API server for testing..."
    
    # Start ComfyUI in the background
    if [ "$FORCE_CPU" = "true" ]; then
        echo "Starting ComfyUI in CPU mode..."
        python main.py --listen 0.0.0.0 --port 8188 --cpu &
    else
        echo "Starting ComfyUI in GPU mode..."
        python main.py --listen 0.0.0.0 --port 8188 &
    fi
    COMFY_PID=$!
    
    # Wait for ComfyUI to be ready
    echo "Waiting for ComfyUI to be ready..."
    sleep 45
    
    # Start the local API server for testing
    echo "Starting local API server for testing..."
    cd /src
    python api_server.py
    
    # Clean up
    kill $COMFY_PID 2>/dev/null || true
else
    # Production mode: Start ComfyUI first, then RunPod handler
    echo "Starting ComfyUI server for production..."
    
    # Start ComfyUI in the background
    if [ "$FORCE_CPU" = "true" ]; then
        echo "Starting ComfyUI in CPU mode..."
        python main.py --listen 0.0.0.0 --port 8188 --cpu &
    else
        echo "Starting ComfyUI in GPU mode..."
        python main.py --listen 0.0.0.0 --port 8188 &
    fi
    COMFY_PID=$!
    
    # Wait for ComfyUI to be ready
    echo "Waiting for ComfyUI to be ready..."
    sleep 45
    
    # Verify ComfyUI is running
    echo "Checking ComfyUI health..."
    if python -c "import requests; requests.get('http://127.0.0.1:8188/system_stats', timeout=5)" 2>/dev/null; then
        echo " ComfyUI is ready and responding"
    else
        echo " ComfyUI failed to start properly"
        exit 1
    fi
    
    # Start the RunPod handler
    echo "Starting RunPod handler in production mode..."
    cd /src
    python handler.py
    
    # Clean up (this will run when handler exits)
    echo "Cleaning up..."
    kill $COMFY_PID 2>/dev/null || true
fi
