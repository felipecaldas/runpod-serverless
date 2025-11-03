# Docker Image Optimization Journey: From 203GB to 97GB

## Executive Summary

**Objective**: Build an optimized Docker image for ComfyUI with AI models for RunPod deployment.

**Initial Result**: 203GB bloated image  
**Final Result**: 97.1GB optimized image  
**Time Invested**: ~30 hours  
**Space Saved**: 106GB (52% reduction)

---

## Challenge 0: Single-Stage Build Performance Issues

### Initial Problem: No Build Caching
**Original Dockerfile Structure**: Single-stage build with everything in sequence.

**Implementation**:
```dockerfile
FROM runpod/worker-comfyui:5.1.0-base
WORKDIR /comfyui

# Install custom nodes
RUN comfy-node-install https://github.com/city96/ComfyUI-GGUF
RUN comfy-node-install https://github.com/Fannovel16/ComfyUI-Frame-Interpolation
RUN comfy-node-install https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite
# ... more custom nodes

# Install Python packages
RUN pip install gguf sentencepiece protobuf ...

# Download models
RUN wget models...
```

**Problems Encountered**:
1. **No layer caching**: Every code change invalidated all subsequent layers
2. **45+ minute rebuilds**: Custom node installation took ~45 minutes every time
3. **Wasted time**: Even minor Dockerfile changes required full custom node reinstall
4. **Poor developer experience**: Iteration was painfully slow

**Why It Failed**: Docker's layer caching is invalidated from the point of change downward. Any modification to model downloads or final steps would force a complete rebuild of custom nodes.

### Solution: Multi-Stage Build Architecture

**New Approach**: Separate build stages for different concerns.

**Implementation**:
```dockerfile
# Stage 1: Custom nodes (cached separately)
FROM runpod/worker-comfyui:5.1.0-base AS custom_nodes
RUN comfy-node-install https://github.com/city96/ComfyUI-GGUF
RUN comfy-node-install https://github.com/Fannovel16/ComfyUI-Frame-Interpolation
# ... more custom nodes

# Stage 2: Python packages (cached separately)
FROM runpod/worker-comfyui:5.1.0-base AS packages
RUN pip install gguf sentencepiece protobuf ...

# Stage 3: Final image (combines everything)
FROM runpod/worker-comfyui:5.1.0-base
COPY --from=packages /opt/venv /opt/venv
COPY --from=custom_nodes /comfyui/custom_nodes /comfyui/custom_nodes
RUN wget models...
```

**Benefits Achieved**:
- ✅ **Independent caching**: Custom nodes cached separately from models
- ✅ **Fast iterations**: Model changes don't trigger custom node reinstalls
- ✅ **Build time reduction**: 45 minutes of custom node installation skipped for model-only changes, which is there it gave me more headaches (see Challenge 1)
- ✅ **Better organization**: Clear separation of concerns

**Impact**: This multi-stage approach was essential before tackling the layer bloat problem. Without it, debugging the COPY vs wget issue would have taken even longer due to 45-minute rebuild cycles.

---

## Challenge 1: COPY vs wget - The Layer Bloat Problem

### Initial Approach: Local COPY Commands
**Strategy**: Download models locally to `G:\ComfyUI_windows_portable\ComfyUI\models\`, then COPY them into the Docker image.

**Implementation**:
```dockerfile
COPY vae/wan_2.1_vae.safetensors models/vae/
COPY vae/wan2.2_vae.safetensors models/vae/
COPY vae/qwen_image_vae.safetensors models/vae/
# ... 15 total COPY commands
```

**Problems Encountered**:
1. **Each COPY creates a separate Docker layer** (15 layers for 15 files)
2. **Layer duplication**: Docker's layered filesystem kept intermediate states
3. **Image bloat**: 203GB image despite only 87GB actual content (verified the content size with `du -BG --max-depth=1 / | sort -n`)
4. **Windows path issues**: Build context problems with large files

**Why It Failed**: Docker's copy-on-write filesystem creates a new layer for each COPY instruction, and these layers accumulate without proper squashing.

---

## Challenge 2: The Squashing Saga

### Attempt 1: `docker buildx build --squash`
**Command**:
```powershell
docker buildx build --platform linux/amd64 --squash `
  -f .\Dockerfile.runpod `
  -t fcaldas/comfyui.tabario.com:1.0 `
  --load .
```

**Result**: ❌ **FAILED**  
- `--squash` flag doesn't work properly with `docker buildx` on Windows
- Image remained 203GB
- Layers were not flattened

### Attempt 2: `docker build --squash`
**Command**:
```powershell
$env:DOCKER_CLI_EXPERIMENTAL = "enabled"
docker build --squash `
  -f .\Dockerfile.runpod `
  -t fcaldas/comfyui.tabario.com:1.0 .
```

**Result**: ❌ **FAILED**  
- Squash didn't activate (Windows Docker Desktop limitation)
- Image still 177GB
- No layer consolidation occurred

---

## Challenge 3: Post-Build Flattening Attempts

### Attempt 1: `docker export | docker import`
**Command**:
```powershell
docker export temp_squash | docker import - fcaldas/comfyui.tabario.com:1.0-flat
```

**Result**: ❌ **CATASTROPHIC FAILURE**  
**Error**: `Array dimensions exceeded supported range`

**Root Cause**: 
- PowerShell pipes buffer data in memory
- 87GB tar stream exceeded PowerShell's array size limit (~2GB on Windows)
- Process ran for **4 hours** before failing

### Attempt 2: `docker commit`
**Command**:
```powershell
docker commit temp_flatten fcaldas/comfyui.tabario.com:1.0-flat
```

**Result**: ❌ **FAILED**  
- Image remained 177GB
- `docker commit` doesn't flatten layers, just adds a new layer on top
- Misconception about how commit works

### Attempt 3: `docker export` to file + `docker import`
**Command**:
```powershell
docker export temp_flatten -o G:\comfyui-flat.tar
docker import G:\comfyui-flat.tar fcaldas/comfyui.tabario.com:1.0-flat-real
```

**Result**: ❌ **FAILED**  
- Image still 177GB
- Export/import process took hours
- No actual size reduction achieved

**Conclusion**: **Post-build flattening is ineffective** - the bloat is structural, not just layer duplication.

---

## Challenge 4: Understanding the Real Problem

### The Revelation
After extensive testing, we discovered:

**Image Size Breakdown**:
```
Base image (runpod/worker-comfyui:5.1.0-base): ~60GB
  - CUDA toolkit: ~3GB
  - Python + dependencies: ~10GB
  - ComfyUI framework: ~10GB
  - NVIDIA libraries: ~2GB
  - System packages: ~35GB

Your models (15 COPY layers): ~79GB
Overhead from layer duplication: ~64GB

Total: 203GB
```

**Key Insight**: The problem wasn't just squashing - it was:
1. Too many COPY layers creating duplication
2. Downloading unnecessary models
3. Base image already being massive

---

## The Solution: wget in Single RUN Layer

### Final Approach
**Strategy**: Use a single `RUN` command with chained `wget` downloads.

**Why This Works**:
- ✅ **Single layer**: All downloads happen in one RUN instruction
- ✅ **No duplication**: No intermediate COPY layers
- ✅ **No local dependencies**: Downloads directly from HuggingFace
- ✅ **Reproducible**: Anyone can build without local files
- ✅ **Works with standard docker build**: No experimental features needed

**Implementation**:
```dockerfile
RUN mkdir -p custom_nodes/comfyui-frame-interpolation/ckpts/rife \
 && wget -O models/vae/wan_2.1_vae.safetensors https://... \
 && wget -O models/clip/umt5-xxl-encoder-Q5_K_M.gguf https://... \
 && wget -O models/diffusion_models/Wan2.2-I2V-A14B-HighNoise-Q8_0.gguf https://... \
 && wget -O models/diffusion_models/Wan2.2-I2V-A14B-LowNoise-Q8_0.gguf https://... \
 && wget -O models/loras/Wan22_A14B_T2V_HIGH_Lightning_4steps_lora_250928_rank128_fp16.safetensors https://... \
 && wget -O models/loras/Wan22_A14B_T2V_LOW_Lightning_4steps_lora_250928_rank64_fp16.safetensors https://... \
 && wget -O custom_nodes/comfyui-frame-interpolation/ckpts/rife/rife47.pth https://... \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
```

### Additional Optimization: Minimal Model Set
**Analysis**: Reviewed workflow JSON to identify only required models.

**Removed unnecessary models**:
- ❌ `wan2.2_vae.safetensors`
- ❌ `qwen_image_vae.safetensors`
- ❌ `illustriousXL_v01.safetensors`
- ❌ `v1-5-pruned-emaonly-fp16.safetensors`
- ❌ `chromaAnimeAIO_chromaAnimeAIOV1FP8.safetensors`
- ❌ `RealESRGAN_x2plus.pth`
- ❌ `qwen_2.5_vl_7b_fp8_scaled.safetensors`
- ❌ `Qwen_Image_Distill-Q8_0.gguf`

**Kept only required models** (7 files, ~37GB):
- ✅ `wan_2.1_vae.safetensors` (254MB)
- ✅ `umt5-xxl-encoder-Q5_K_M.gguf` (4.15GB)
- ✅ `Wan2.2-I2V-A14B-HighNoise-Q8_0.gguf` (15.4GB)
- ✅ `Wan2.2-I2V-A14B-LowNoise-Q8_0.gguf` (15.4GB)
- ✅ `Wan22_A14B_T2V_HIGH_Lightning_4steps_lora_250928_rank128_fp16.safetensors` (1.23GB)
- ✅ `Wan22_A14B_T2V_LOW_Lightning_4steps_lora_250928_rank64_fp16.safetensors` (614MB)
- ✅ `rife47.pth` (21MB)

**Model reduction**: 79GB → 37GB (saved 42GB)

---

## Final Results

### Image Size Comparison
| Version | Size | Models | Layers |
|---------|------|--------|--------|
| Original (COPY) | 203GB | 15 files (79GB) | 15+ layers |
| wget (all models) | 177GB | 15 files (79GB) | 1 layer |
| **wget (minimal)** | **97.1GB** | **7 files (37GB)** | **1 layer** |

### Build Command
```powershell
cd y:\projects\edit-videos

docker build `
  -f .\Dockerfile.runpod.wan22 `
  -t fcaldas/tabario.com:1.0-wan22 `
  .
```

---

## Lessons Learned

### 1. **Docker Layer Optimization**
- Multiple COPY commands = multiple layers = bloat
- Single RUN with chained commands = single layer = optimal
- Squashing doesn't work reliably on Windows Docker Desktop

### 2. **Windows PowerShell Limitations**
- Pipes cannot handle large binary streams (>2GB)
- `docker export | docker import` fails with large images
- Use file-based export or avoid pipes entirely

### 3. **Base Image Impact**
- `runpod/worker-comfyui:5.1.0-base` is ~60GB alone
- Can't reduce below base image size without rebuilding from scratch
- Choose base images carefully

### 4. **Model Selection Matters**
- Analyze workflow requirements before downloading everything
- 42GB saved by removing unused models
- Workflow-specific images are more efficient

### 5. **Build vs Post-Build Optimization**
- Fix architecture during build, not after
- Post-build flattening is unreliable and time-consuming
- Proper Dockerfile structure > post-processing tricks

---

## Recommendations for Future Builds

1. **Always use single RUN for large downloads**
   ```dockerfile
   RUN wget file1 && wget file2 && wget file3
   ```

2. **Analyze dependencies first**
   - Review workflow JSON
   - Download only required models
   - Avoid "just in case" bloat

3. **Use standard `docker build`**
   - Skip buildx unless multi-platform needed
   - Avoid experimental flags
   - Keep it simple

4. **Test incrementally**
   - Build with 1-2 models first
   - Verify size and functionality
   - Scale up gradually

5. **Document model sources**
   - Keep URLs in Dockerfile comments
   - Track model versions
   - Enable reproducible builds

---

## Time Investment Breakdown

| Activity | Time Spent |
|----------|-----------|
| Initial research & setup | 2 hours |
| Downloading models locally | 4 hours |
| Failed COPY approach builds | 6 hours |
| Squashing attempts | 3 hours |
| Export/import failures | 8 hours |
| Debugging & troubleshooting | 5 hours |
| Final wget implementation | 2 hours |
| **Total** | **~30 hours** |

---

## Conclusion

The journey from 203GB to 97.1GB was painful but educational. The key takeaway: **Docker image optimization requires understanding the layered filesystem architecture**. Post-build tricks like squashing and export/import are unreliable band-aids. The real solution is proper Dockerfile structure with single-layer operations and minimal dependencies.

**Final achievement**: A production-ready, 97.1GB Docker image optimized for the I2V-Wan-2.2-Lightning workflow, ready for deployment to RunPod.
