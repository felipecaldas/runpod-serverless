# Build and Deploy a RunPod Serverless Pod for Wan 2.2 I2V (ComfyUI)

This guide walks you through building the Docker image, creating a RunPod Network Volume for models, populating it, creating a Serverless endpoint, and testing it.

Works on Windows 11 PowerShell and uses Docker Hub as the registry.

---

## 1) Prerequisites

- Docker Desktop with buildx and WSL2 backend enabled
- A Docker Hub account (free, public images)
- RunPod account with billing enabled
- Your repo contains `Dockerfile.runpod` (custom nodes only; models via Network Volume)

---

## 2) Build locally and push to Docker Hub

**Build the optimized image** (97GB, minimal models for I2V-Wan-2.2-Lightning workflow):

```powershell
cd y:\projects\edit-videos

docker build `
  -f .\Dockerfile.runpod.serverless.v3 `
  -t fcaldas/tabario.com:1.0-wan22 `
  .
```

**Note**: This uses `Dockerfile.runpod.serverless.v3` which:
- Downloads only 7 required models (~37GB) via wget in a single RUN layer
- Uses multi-stage builds for optimal caching
- Results in a 97GB image (vs 177GB with all models)
- No squashing needed - already optimized

See `docker-image-optimization-journey.md` for the full story of how we got here.

### 2.1) Run locally to validate (CPU-only quick check)

```powershell
docker run --rm -it `
  -e CUDA_VISIBLE_DEVICES="" `
  -p 8188:8188 `
  fcaldas/tabario.com:1.0-wan22 `
  bash -lc "cd /comfyui && /opt/venv/bin/python main.py --listen 0.0.0.0 --port 8188 --cpu"
```

Open http://localhost:8188 and confirm ComfyUI starts and lists installed custom nodes.

### 2.2) Run locally with GPU (if NVIDIA Container Toolkit is configured)

```powershell
docker run --rm -it `
  --gpus all `
  -p 8188:8188 `
  fcaldas/tabario.com:1.0-wan22 `
  bash -lc "cd /comfyui && /opt/venv/bin/python main.py --listen 0.0.0.0 --port 8188"
```

Validate in http://localhost:8188. If GPU is not detected, install latest NVIDIA driver and enable GPU in Docker Desktop (WSL2).

### 2.3) Optional: Test the serverless worker locally

```powershell
docker run --rm -it `
  -e SERVE_API_LOCALLY=true `
  -p 3000:3000 `
  -v C:\path\to\test_input.json:/workspace/test_input.json `
  fcaldas/tabario.com:1.0-wan22
```

This serves the worker API locally on port 3000 and consumes `/workspace/test_input.json` if present.

- Verify custom nodes were installed:

```powershell
docker run --rm fcaldas/tabario.com:1.0-wan22 bash -lc "ls -1 /comfyui/custom_nodes"
```

Expected directories include:
- ComfyUI-GGUF (or comfyui-gguf)
- ComfyUI-Frame-Interpolation
- ComfyUI-VideoHelperSuite
- ComfyUI_ExtraModels
- ComfyUI-Unload-Model
- ComfyUI-Easy-Use

### 2.4) Push to Docker Hub (required for RunPod deployment)

```powershell
docker login
docker push fcaldas/tabario.com:1.0-wan22
```

Use this image string in RunPod: `fcaldas/tabario.com:1.0-wan22`

---

## 3) Local Testing and Validation

Before pushing to Docker Hub, validate the image works correctly:

### 3.1) Test ComfyUI UI (CPU-only)
```powershell
docker run --rm -it `
  -e CUDA_VISIBLE_DEVICES="" `
  -p 8188:8188 `
  fcaldas/tabario.com:1.0-wan22 `
  bash -lc "cd /comfyui && /opt/venv/bin/python main.py --listen 0.0.0.0 --port 8188 --cpu"
```
Open http://localhost:8188 and confirm:
- ComfyUI starts successfully
- All custom nodes are installed (check the settings)
- All models are visible in the model loader

### 3.2) Test with GPU (if available)
```powershell
docker run --rm -it `
  --gpus all `
  -p 8188:8188 `
  fcaldas/tabario.com:1.0-wan22 `
  bash -lc "cd /comfyui && /opt/venv/bin/python main.py --listen 0.0.0.0 --port 8188"
```

### 3.3) Test serverless worker API
```powershell
docker run --rm -it `
  -e SERVE_API_LOCALLY=true `
  -p 3000:3000 `
  -v C:\path\to\test_input.json:/workspace/test_input.json `
  fcaldas/tabario.com:1.0-wan22
```

### 3.4) Verify models and custom nodes
```powershell
# Check custom nodes
docker run --rm fcaldas/tabario.com:1.0-wan22 bash -lc "ls -1 /comfyui/custom_nodes"

# Check models
docker run --rm fcaldas/tabario.com:1.0-wan22 bash -lc "find /comfyui/models -type f -name '*.safetensors' -o -name '*.gguf' -o -name '*.pth' | sort"
```

Expected models (minimal set for I2V-Wan-2.2-Lightning workflow):
- wan_2.1_vae.safetensors
- umt5-xxl-encoder-Q5_K_M.gguf
- Wan2.2-I2V-A14B-HighNoise-Q8_0.gguf
- Wan2.2-I2V-A14B-LowNoise-Q8_0.gguf
- Wan22_A14B_T2V_HIGH_Lightning_4steps_lora_250928_rank128_fp16.safetensors
- Wan22_A14B_T2V_LOW_Lightning_4steps_lora_250928_rank64_fp16.safetensors
- rife47.pth

---

## 4) Create RunPod Serverless Endpoint

After pushing to Docker Hub (see section 2.4), create your endpoint:

1. In RunPod → Templates → Create Template
2. Container Image: `fcaldas/tabario.com:1.0-wan22`
3. Container Disk: 100 GB (to accommodate the 97GB image)
4. GPU: Recommended 16-24 GB VRAM for Wan2.2 GGUF models
5. Network Volume: **Not required** (all models are baked into the image)
6. Environment Variables: None needed
7. Ports: 8188 (ComfyUI)

Deploy the template and test with your workflow. The endpoint should start faster since no model downloading is needed.

---

## 5) Test the endpoint

- Use the worker-comfyui API to submit your workflow JSON (the same Wan 2.2 I2V workflow). Ensure prompts and input image variables are set.
- In Serverless → your endpoint → Executions → run a test payload.
- Check Logs for progress and output image/video URLs.

Tip: First run will cache nodes and scan models; subsequent runs are faster.

---

## 6) Troubleshooting

- Empty build logs in RunPod GitHub integration
  - Build locally with `--progress=plain` and `--load` to see full logs.
- Custom node install fails
  - The Docker build will stop at the failing `comfy-node-install` line and show which node failed. Try again later or install from Git URL as a fallback.
- Models not found in ComfyUI
  - Verify models were copied correctly during Docker build
  - Check the build log for any COPY errors
  - Models should be in `/comfyui/models/...` (not `/workspace/models/`)
- Out of VRAM
  - Reduce resolution/length in the workflow, use Q4 models, or select a GPU with more VRAM
- Docker build takes too long
  - Multi-stage builds cache custom nodes separately
  - Model downloads happen only once per build
  - Use `docker build` (not buildx) for simplicity

**Note**: See `docker-image-optimization-journey.md` for detailed troubleshooting of image size issues.

---

## 7) Update image later

When you change models or custom nodes:

```powershell
cd y:\projects\edit-videos

# Build with new version tag
docker build `
  -f .\Dockerfile.runpod.serverless.v3 `
  -t fcaldas/tabario.com:1.1-wan22 `
  .

# Test locally first
docker run --rm -it `
  -e CUDA_VISIBLE_DEVICES="" `
  -p 8188:8188 `
  fcaldas/tabario.com:1.1-wan22 `
  bash -lc "cd /comfyui && /opt/venv/bin/python main.py --listen 0.0.0.0 --port 8188 --cpu"

# If tests pass, push to Docker Hub
docker login
docker push fcaldas/tabario.com:1.1-wan22
```

Update your RunPod template to use the new image tag (1.1-wan22).

---