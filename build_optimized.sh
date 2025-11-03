#!/bin/bash

# Build script for optimized RunPod serverless ComfyUI worker v2
# This creates a smaller, serverless-friendly image with runtime model downloads
# and production-grade handler based on official worker-comfyui

set -e

echo "Building optimized RunPod serverless ComfyUI worker v2..."

# Build arguments
IMAGE_NAME="fcaldas/tabario.com"
IMAGE_TAG="2.0-optimized-v2"
DOCKERFILE="Dockerfile.runpod.serverless.v2"

echo "Building image: $IMAGE_NAME:$IMAGE_TAG"
echo "Using Dockerfile: $DOCKERFILE"
echo "Features:"
echo "  - Multi-stage build for optimal caching"
echo "  - Runtime model downloads (~37GB)"
echo "  - Production-grade handler with validation"
echo "  - Resource monitoring and logging"
echo "  - WebSocket-based workflow monitoring"

# Build the Docker image
docker build \
    --platform linux/amd64 \
    -f "$DOCKERFILE" \
    -t "$IMAGE_NAME:$IMAGE_TAG" \
    .

echo "Build completed successfully!"
echo ""
echo "Image details:"
docker images | grep "$IMAGE_NAME" | grep "$IMAGE_TAG"

echo ""
echo "=== Architecture Comparison ==="
echo "Original (v1):    97GB image, models baked in"
echo "Optimized (v2):   ~5GB image, models downloaded at runtime"
echo "Handler:          Production-grade with validation & monitoring"
echo ""

echo "=== Quick Test Commands ==="
echo "Test locally:"
echo "  docker run --rm -it -p 8188:8188 $IMAGE_NAME:$IMAGE_TAG"
echo ""
echo "Test with model downloads:"
echo "  docker run --rm -it -e SERVE_API_LOCALLY=true -p 3000:3000 $IMAGE_NAME:$IMAGE_TAG"
echo ""

echo "=== Deployment ==="
echo "Push to Docker Hub:"
echo "  docker login"
echo "  docker push $IMAGE_NAME:$IMAGE_TAG"
echo ""
echo "Use in RunPod endpoint configuration:"
echo "  Image: $IMAGE_NAME:$IMAGE_TAG"
echo ""

echo "=== Performance ==="
echo "Expected performance:"
echo "  - Image pull: 1-2 minutes (vs 10-15 minutes)"
echo "  - Cold start: 2-4 minutes (includes model downloads)"
echo "  - Subsequent requests: Instant (models cached)"
echo "  - Memory usage: Optimized with resource monitoring"
echo "  - Error handling: Production-grade with detailed logging"
