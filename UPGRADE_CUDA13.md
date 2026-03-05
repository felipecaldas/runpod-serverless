# CUDA 13 Upgrade Plan

## Goal

Upgrade the base Docker image from CUDA 12.4 to CUDA 13.0+ to unlock optimized ComfyUI
compute backends (`comfy_kitchen` CUDA and Triton) and benefit from newer PyTorch features.

## Current State

- **Base image**: `nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04`
- **PyTorch**: `torch==2.4.1` (cu124)
- **ComfyUI warning**: `You need pytorch with cu130 or higher to use optimized CUDA operations`
- **comfy_kitchen backends**: CUDA ❌ disabled, Triton ❌ disabled, eager ✅ active

## Target State

- **Base image**: `nvidia/cuda:13.0.0-cudnn-devel-ubuntu22.04`
  - Docker Hub: https://hub.docker.com/layers/nvidia/cuda/13.0.0-cudnn-devel-ubuntu22.04/images/sha256-63d2349dda93711cbbfde6f5a1fe81a664c413bf7a10a6e381d54b9e5cd97e7c
- **PyTorch**: Latest stable with cu130 wheel
  - Index: https://download.pytorch.org/whl/cu130
- **comfy_kitchen backends**: CUDA ✅, Triton ✅

## Expected Benefits

- **Optimized CUDA kernels** for `apply_rope`, `scaled_mm_nvfp4`, quantize/dequantize ops
  — directly benefits GGUF quantized models like `seedvr2_ema_3b-Q4_K_M.gguf`
- **Newer PyTorch** (2.6+) brings improved `torch.compile`, better memory management, SDPA improvements
- **Future-proofing** as ComfyUI and custom nodes move toward requiring newer CUDA

## Steps

1. Create a feature branch (e.g., `feat-cuda13-upgrade`)
2. Update `Dockerfile.custom` and `Dockerfile.base`:
   - Change base image to `nvidia/cuda:13.0.0-cudnn-devel-ubuntu22.04`
   - Change PyTorch install to: `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130`
3. Build the image locally and verify it compiles without errors
4. Push to registry and deploy to a RunPod test pod
5. Run the following test workflows end-to-end:
   - `seedvr2_video_upscale` (GGUF quantized DiT + RIFE frame interpolation)
   - `I2V-Wan-2.2-Lightning-runpod` (Wan 2.2 video generation)
   - Any image generation workflow
6. Verify in logs that `comfy_kitchen` CUDA and Triton backends show `disabled: False`
7. Compare performance (FPS, total time) against the CUDA 12.4 baseline
8. If all passes, merge and tag a new release

## Risks & Things to Watch

### RunPod GPU Driver Compatibility
- **CUDA 13.0 requires NVIDIA driver 570+**
- RunPod Serverless GPU endpoints explicitly support CUDA 13.0 as a valid option in the `allowedCudaVersions` field
- When creating or updating endpoints, set `

### Custom Node Compatibility
- **ComfyUI-GGUF**: Uses compiled extensions for GGUF loading — verify it works with new PyTorch/CUDA
- **ComfyUI-SeedVR2_VideoUpscaler**: Has its own CUDA operations — test thoroughly
- **ComfyUI-Frame-Interpolation**: RIFE model inference should be fine but verify
- **ComfyUI-Easy-Use**: Large node pack, may have hidden CUDA dependencies

### PyTorch cu130 Wheel Maturity
- cu130 wheels may still be nightly or early-release quality
- Check the PyTorch release notes to confirm cu130 is in a stable release, not just nightly
- If only nightly, consider waiting for a stable release

### Image Size
- Current image is ~25GB
- Newer CUDA devel images may be larger — monitor the final image size
- Consider switching to `runtime` instead of `devel` if build-time CUDA compilation is not needed

## RunPod Serverless Configuration

To ensure the endpoint uses workers with CUDA 13.0 support, configure the endpoint with:

```json
{
  "allowedCudaVersions": [
    "13.0"
  ]
}
```

This restricts the endpoint to only use workers whose host CUDA version is 13.0.

**Note**: The worker image itself requires CUDA ≥ 12.1 inside the container, but can run on hosts with CUDA 13.0 drivers.

Example API call for creating an endpoint:

```bash
curl --request POST \
  --url https://rest.runpod.io/v1/endpoints \
  --header 'Authorization: Bearer <token>' \
  --header 'Content-Type: application/json' \
  --data '{
    "templateId": "30zmvf89kd",
    "allowedCudaVersions": [
      "13.0"
    ],
    "computeType": "GPU",
    "gpuTypeIds": [
      "NVIDIA GeForce RTX 4090"
    ],
    ...other configuration...
  }'
```

Keep the CUDA 12.4 image tagged and available. If CUDA 13 causes issues on RunPod,
revert to the previous tag immediately.
