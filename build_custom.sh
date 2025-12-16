#!/bin/bash

# Build script for custom ComfyUI RunPod serverless worker
# Built from CUDA base to avoid compatibility issues with runpod/worker-comfyui:5.1.0-base

set -e

echo "Building custom ComfyUI RunPod serverless worker (CUDA base + optimizations)..."

# Build arguments
IMAGE_NAME="fcaldas/tabario.com"
IMAGE_TAG="1.3"
DOCKERFILE="Dockerfile.custom"

echo "Building image: $IMAGE_NAME:$IMAGE_TAG"
echo "Using Dockerfile: $DOCKERFILE"
echo ""
echo "=== Architecture ==="
echo "Base:          nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04 (CUDA base)"
echo "Custom nodes:  Installed via git clone (more reliable)"
echo "Models:        Provided via RunPod network volume (symlinked at runtime)"
echo "Handler:       Production-grade with validation"
echo "Features:"
echo "  ✅ Custom CUDA base build"
echo "  ✅ Latest ComfyUI from source"
echo "  ✅ Optimized multi-stage builds"
echo "  ✅ Shared models via network volume symlinks"
echo "  ✅ Enhanced logging and monitoring"
echo "  ✅ Resource monitoring"
echo "  ✅ WebSocket-based workflow monitoring"

# Build arguments
BUILD_ARGS=""
BUILD_ARGS+=" --build-arg GGUF_REF=main"
BUILD_ARGS+=" --build-arg VFI_REF=main"
BUILD_ARGS+=" --build-arg VHS_REF=main"

# Build the Docker image
docker build \
    --platform linux/amd64 \
    -f "$DOCKERFILE" \
    -t "$IMAGE_NAME:$IMAGE_TAG" \
    $BUILD_ARGS \
    .

echo ""
echo "✅ Build completed successfully!"
echo ""
echo "📋 Image details:"
docker images "$IMAGE_NAME:$IMAGE_TAG"

echo ""
echo "🧪 To test locally:"
echo "docker run --rm -p 8188:8188 -v /path/to/models:/runpod-volume/comfyui/models $IMAGE_NAME:$IMAGE_TAG"

echo ""
echo "🚀 To push to registry:"
echo "docker push $IMAGE_NAME:$IMAGE_TAG"
