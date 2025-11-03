#!/bin/bash

# Model download script for RunPod serverless ComfyUI worker
# Downloads required models at container startup to keep image size small

set -e

echo "Starting model downloads for ComfyUI..."

# Change to ComfyUI directory
cd /comfyui

# Function to download with retry
download_with_retry() {
    local url="$1"
    local output="$2"
    local max_retries=3
    local retry_delay=5
    
    for ((i=1; i<=max_retries; i++)); do
        echo "Downloading $output (attempt $i/$max_retries)..."
        if wget -O "$output" "$url" --timeout=30 --tries=1; then
            echo "Successfully downloaded $output"
            return 0
        else
            echo "Failed to download $output (attempt $i/$max_retries)"
            if [ $i -lt $max_retries ]; then
                echo "Retrying in $retry_delay seconds..."
                sleep $retry_delay
            else
                echo "Failed to download $output after $max_retries attempts"
                return 1
            fi
        fi
    done
}

# Download VAE models
echo "Downloading VAE models..."
download_with_retry "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors" \
    "models/vae/wan_2.1_vae.safetensors"

download_with_retry "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors" \
    "models/vae/wan2.2_vae.safetensors"

download_with_retry "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors" \
    "models/vae/qwen_image_vae.safetensors"

# Download CLIP models
echo "Downloading CLIP models..."
download_with_retry "https://huggingface.co/city96/umt5-xxl-encoder-gguf/resolve/main/umt5-xxl-encoder-Q5_K_M.gguf" \
    "models/clip/umt5-xxl-encoder-Q5_K_M.gguf"

# Download checkpoint models
echo "Downloading checkpoint models..."
download_with_retry "https://huggingface.co/frankjoshua/illustriousXL_v01/resolve/main/illustriousXL_v01.safetensors" \
    "models/checkpoints/illustriousXL_v01.safetensors"

download_with_retry "https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/v1-5-pruned-emaonly-fp16.safetensors" \
    "models/checkpoints/v1-5-pruned-emaonly-fp16.safetensors"

# Download upscale models
echo "Downloading upscale models..."
download_with_retry "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth" \
    "models/upscale_models/RealESRGAN_x2plus.pth"

# Download text encoder models
echo "Downloading text encoder models..."
download_with_retry "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" \
    "models/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors"

# Download diffusion models
echo "Downloading diffusion models..."
download_with_retry "https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/resolve/main/HighNoise/Wan2.2-I2V-A14B-HighNoise-Q8_0.gguf" \
    "models/diffusion_models/Wan2.2-I2V-A14B-HighNoise-Q8_0.gguf"

download_with_retry "https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/resolve/main/LowNoise/Wan2.2-I2V-A14B-LowNoise-Q8_0.gguf" \
    "models/diffusion_models/Wan2.2-I2V-A14B-LowNoise-Q8_0.gguf"

# Download UNET models
echo "Downloading UNET models..."
download_with_retry "https://huggingface.co/QuantStack/Qwen-Image-Distill-GGUF/resolve/main/Qwen_Image_Distill-Q8_0.gguf" \
    "models/unet/Qwen_Image_Distill-Q8_0.gguf"

# Download LoRA models
echo "Downloading LoRA models..."
download_with_retry "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/Wan22_A14B_T2V_HIGH_Lightning_4steps_lora_250928_rank128_fp16.safetensors" \
    "models/loras/Wan22_A14B_T2V_HIGH_Lightning_4steps_lora_250928_rank128_fp16.safetensors"

download_with_retry "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/Wan22_A14B_T2V_LOW_Lightning_4steps_lora_250928_rank64_fp16.safetensors" \
    "models/loras/Wan22_A14B_T2V_LOW_Lightning_4steps_lora_250928_rank64_fp16.safetensors"

# Download frame interpolation model
echo "Downloading frame interpolation model..."
download_with_retry "https://huggingface.co/wavespeed/misc/resolve/main/rife/rife47.pth" \
    "custom_nodes/comfyui-frame-interpolation/ckpts/rife/rife47.pth"

# Clean up
echo "Cleaning up temporary files..."
apt-get clean
rm -rf /tmp/* /var/tmp/*

echo "Model downloads completed successfully!"
echo "Total model size:"
du -sh /comfyui/models/

echo "Available models:"
find /comfyui/models -type f -name "*.safetensors" -o -name "*.gguf" -o -name "*.pth" | sort
