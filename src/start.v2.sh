#!/bin/bash

# Optimized start script for RunPod serverless worker with ComfyUI
# Downloads models at runtime then starts services

set -e

echo "Starting optimized RunPod serverless worker with ComfyUI v2..."

# Set working directory
cd /comfyui

# Activate virtual environment
source /opt/venv/bin/activate

# Download models at runtime (only if not already present)
if [ ! -f "/comfyui/models/checkpoints/v1-5-pruned-emaonly-fp16.safetensors" ]; then
    echo "Models not found, downloading at runtime..."
    /src/download_models.sh
else
    echo "Models already present, skipping download"
fi

# Start ComfyUI in the background
echo "Starting ComfyUI server..."
# Use CPU mode for testing when no GPU is available
if [ "$CUDA_VISIBLE_DEVICES" = "" ] || [ "$FORCE_CPU" = "true" ]; then
    echo "Starting ComfyUI in CPU mode..."
    python main.py --listen 0.0.0.0 --port 8188 --cpu &
else
    echo "Starting ComfyUI in GPU mode..."
    python main.py --listen 0.0.0.0 --port 8188 &
fi
COMFY_PID=$!

# Wait for ComfyUI to be ready
echo "Waiting for ComfyUI to be ready..."
echo "ComfyUI typically takes 30-60 seconds to start..."
sleep 45

echo "Starting RunPod handler..."

# Check if we should run container tests
if [ "$RUN_CONTAINER_TESTS" = "true" ]; then
    echo "Running container tests..."
    # Wait a bit more for ComfyUI to fully initialize
    sleep 10
    # Run the container test suite
    python /src/test_container.py
    TEST_RESULT=$?
    
    echo "Container tests completed with exit code: $TEST_RESULT}"
fi

# Start the RunPod handler (production mode)
echo "Starting RunPod handler in production mode..."
cd /src
python handler.py

# Clean up
kill $COMFY_PID 2>/dev/null || true
