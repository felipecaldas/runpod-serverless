#!/bin/bash

# Build script for RunPod serverless ComfyUI worker v3
# Based on official runpod/worker-comfyui:5.1.0-base with our optimizations

set -e

echo "Building RunPod serverless ComfyUI worker v3 (official base + optimizations)..."

# Build arguments
IMAGE_NAME="fcaldas/tabario.com"
IMAGE_TAG="1.0-wan22"
DOCKERFILE="Dockerfile.runpod.serverless"

echo "Building image: $IMAGE_NAME:$IMAGE_TAG"
echo "Using Dockerfile: $DOCKERFILE"
echo ""
echo "=== Architecture ==="
echo "Base:          runpod/worker-comfyui:5.1.0-base (official)"
echo "Custom nodes:  Installed via comfy-node-install"
echo "Models:        Downloaded at runtime (~37GB)"
echo "Handler:       Production-grade with validation"
echo "Features:"
echo "  ✅ Official RunPod compatibility"
echo "  ✅ Optimized multi-stage builds"
echo "  ✅ Runtime model downloads"
echo "  ✅ Enhanced logging and monitoring"
echo "  ✅ Resource monitoring"
echo "  ✅ WebSocket-based workflow monitoring"

# Build the Docker image
docker build \
    --platform linux/amd64 \
    -f "$DOCKERFILE" \
    -t "$IMAGE_NAME:$IMAGE_TAG" \
    .

echo ""
echo "Build completed successfully!"
echo ""
echo "Image details:"
docker images | grep "$IMAGE_NAME" | grep "$IMAGE_TAG"

echo ""
echo "=== Advantages of v3 ==="
echo "✅ Official RunPod base image - maximum compatibility"
echo "✅ Uses comfy-node-install - proper custom node installation"
echo "✅ Production-tested environment"
echo "✅ Runtime model optimization"
echo "✅ Enhanced handler with monitoring"
echo ""

echo "=== Quick Test Commands ==="
echo "Test production handler:"
echo "  docker run --rm -it $IMAGE_NAME:$IMAGE_TAG"
echo ""
echo "Test with local API server:"
echo "  docker run --rm -it -e SERVE_API_LOCALLY=true -p 8188:8188 $IMAGE_NAME:$IMAGE_TAG"
echo ""

echo "=== Deployment ==="
echo "Push to Docker Hub:"
echo "  docker login"
echo "  docker push $IMAGE_NAME:$IMAGE_TAG"
echo ""
echo "Use in RunPod endpoint:"
echo "  Image: $IMAGE_NAME:$IMAGE_TAG"
echo ""

echo "=== Expected Performance ==="
echo "  - Image size: ~15-20GB (official base + optimizations)"
echo "  - Build time: 5-10 minutes (official base is larger)"
echo "  - Deploy time: 3-5 minutes (larger but more reliable)"
echo "  - Cold start: 3-5 minutes (includes model downloads)"
echo "  - Compatibility: 100% with RunPod serverless"
echo "  - Reliability: Production-tested official base"
