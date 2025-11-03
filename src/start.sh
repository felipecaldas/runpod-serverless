#!/bin/bash

# Start script for RunPod serverless worker with ComfyUI
# This script starts ComfyUI in the background and then launches the RunPod handler

set -e

echo "Starting RunPod serverless worker with ComfyUI..."

# Set working directory
cd /comfyui

# Activate virtual environment
source /opt/venv/bin/activate

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

echo "Starting RunPod handler API..."

# Check if we should run container tests
if [ "$RUN_CONTAINER_TESTS" = "true" ]; then
    echo "Running container tests..."
    # Wait a bit more for ComfyUI to fully initialize
    sleep 10
    # Run the container test suite
    python /src/test_container.py
    TEST_RESULT=$?
    
    echo "Container tests completed with exit code: $TEST_RESULT"
fi

# Start the RunPod handler API
cd /src
echo "Starting RunPod handler API locally for testing..."
python /src/api_server.py

# Clean up
kill $COMFY_PID 2>/dev/null || true
