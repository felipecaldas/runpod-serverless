#!/bin/bash

# Quick test to debug ComfyUI startup
echo "Starting ComfyUI in CPU mode..."

cd /comfyui
source /opt/venv/bin/activate

# Start ComfyUI in background
python main.py --listen 0.0.0.0 --port 8188 --cpu &
COMFY_PID=$!

echo "Waiting 10 seconds for startup..."
sleep 10

echo "Testing root endpoint:"
curl -v http://127.0.0.1:8188/ 2>&1 | head -20

echo ""
echo "Testing system_stats endpoint:"
curl -v http://127.0.0.1:8188/system_stats 2>&1 | head -20

echo ""
echo "Testing with curl exit code: $?"
echo "ComfyUI process ID: $COMFY_PID"

# Clean up
kill $COMFY_PID 2>/dev/null || true
