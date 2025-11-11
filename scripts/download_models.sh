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

    mkdir -p "$(dirname "$output")"
    
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

download_from_civitai() {
    local model_path="$1"
    local output="$2"
    local extra_params="$3"
    local max_retries=3
    local retry_delay=5

    if [[ -z "${CIVITAI_API_KEY:-}" ]]; then
        echo "CIVITAI_API_KEY environment variable is not set but is required for Civitai downloads." >&2
        return 1
    fi

    if [[ -z "$model_path" ]]; then
        echo "Model path is required for Civitai downloads." >&2
        return 1
    fi

    mkdir -p "$(dirname "$output")"

    local base_url="https://civitai.com/api/download/models/${model_path}"
    local url="$base_url"

    if [[ -n "$extra_params" ]]; then
        if [[ "$extra_params" == \?* ]]; then
            url+="$extra_params"
        else
            url+="?$extra_params"
        fi
    fi

    if [[ "$url" == *\?* ]]; then
        url+="&token=${CIVITAI_API_KEY}"
    else
        url+="?token=${CIVITAI_API_KEY}"
    fi

    for ((i=1; i<=max_retries; i++)); do
        echo "Downloading $output from Civitai (attempt $i/$max_retries)..."
        local temp_file="$(mktemp)"
        if wget --quiet --show-progress --content-disposition -O "$temp_file" "$url"; then
            mv "$temp_file" "$output"
            echo "Successfully downloaded $output"
            return 0
        else
            echo "Failed to download $output from Civitai (attempt $i/$max_retries)"
            rm -f "$temp_file"
            if [ $i -lt $max_retries ]; then
                echo "Retrying in $retry_delay seconds..."
                sleep $retry_delay
            else
                echo "Failed to download $output from Civitai after $max_retries attempts"
                return 1
            fi
        fi
    done
}

download_i2v_wan22_models() {
    echo "Downloading models for workflow: i2v-wan22"

    echo "Downloading VAE models..."
    download_with_retry "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_repackaged/resolve/main/vae/wan_2.2_vae.safetensors" \
        "models/vae/wan_2.2_vae.safetensors"
    
    # Additional VAE model required by video_wan2_2_14B_i2v
    download_with_retry "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors" \
        "models/vae/wan_2.1_vae.safetensors"

    echo "Downloading CLIP models..."
    download_with_retry "https://huggingface.co/city96/umt5-xxl-encoder-gguf/resolve/main/umt5-xxl-encoder-Q5_K_M.gguf" \
        "models/clip/umt5-xxl-encoder-Q5_K_M.gguf"
    
    # Additional text encoder required by video_wan2_2_14B_i2v
    download_with_retry "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" \
        "models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"

    echo "Downloading UNet models..."
    download_with_retry "https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/resolve/main/HighNoise/Wan2.2-I2V-A14B-HighNoise-Q8_0.gguf" \
        "models/unet/Wan2.2-I2V-A14B-HighNoise-Q8_0.gguf"
    download_with_retry "https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/resolve/main/LowNoise/Wan2.2-I2V-A14B-LowNoise-Q8_0.gguf" \
        "models/unet/Wan2.2-I2V-A14B-LowNoise-Q8_0.gguf"
    
    # Additional UNet models required by video_wan2_2_14B_i2v
    download_with_retry "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors" \
        "models/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"
    download_with_retry "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors" \
        "models/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"

    echo "Downloading LoRA models..."
    download_with_retry "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/Wan22_A14B_T2V_HIGH_Lightning_4steps_lora_250928_rank128_fp16.safetensors" \
        "models/loras/Wan22_A14B_T2V_HIGH_Lightning_4steps_lora_250928_rank128_fp16.safetensors"
    download_with_retry "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/Wan22_A14B_T2V_LOW_Lightning_4steps_lora_250928_rank64_fp16.safetensors" \
        "models/loras/Wan22_A14B_T2V_LOW_Lightning_4steps_lora_250928_rank64_fp16.safetensors"
    
    # Additional LoRA models required by video_wan2_2_14B_i2v
    download_with_retry "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors" \
        "models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"
    download_with_retry "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors" \
        "models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"

    echo "Downloading frame interpolation model..."
    download_with_retry "https://huggingface.co/wavespeed/misc/resolve/main/rife/rife47.pth" \
        "custom_nodes/comfyui-frame-interpolation/ckpts/rife/rife47.pth"
}

download_t2i_qwen_models() {
    echo "Downloading models for workflow: t2i-qwen"

    echo "Downloading VAE models..."
    download_with_retry "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors" \
        "models/vae/qwen_image_vae.safetensors"

    echo "Downloading CLIP models..."
    download_with_retry "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" \
        "models/clip/qwen_2.5_vl_7b_fp8_scaled.safetensors"

    echo "Downloading UNet models..."
    download_with_retry "https://huggingface.co/QuantStack/Qwen-Image-Distill-GGUF/resolve/main/Qwen_Image_Distill-Q8_0.gguf" \
        "models/unet/Qwen_Image_Distill-Q8_0.gguf"
}

download_t2i_chroma_anime_models() {
    echo "Downloading models for workflow: t2i-chroma-anime"

    echo "Downloading checkpoint models..."
    download_from_civitai "2288507" "models/checkpoints/chromaAnimeAIO_chromaAnimeAIOV1FP8.safetensors" "type=Model&format=SafeTensor&size=pruned&fp=fp8"
}

download_t2i_kids_crayon_models() {
    echo "Downloading models for workflow: t2i-kids-crayon"

    echo "Downloading checkpoint models..."
    download_with_retry "https://huggingface.co/frankjoshua/illustriousXL_v01/resolve/main/illustriousXL_v01.safetensors" \
        "models/checkpoints/illustriousXL_v01.safetensors"

    echo "Downloading upscale models..."
    download_with_retry "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth" \
        "models/upscale_models/RealESRGAN_x2plus.pth"
}

WORKFLOW="${COMFYUI_WORKFLOW:-}"
WORKFLOW="${WORKFLOW//[[:space:]]/}"
WORKFLOW="${WORKFLOW,,}"

if [[ -z "$WORKFLOW" ]]; then
    echo "COMFYUI_WORKFLOW environment variable is not set. Please specify one of: i2v-wan22, t2i-qwen, t2i-chroma-anime, t2i-kids-crayon." >&2
    exit 1
fi

case "$WORKFLOW" in
    i2v-wan22)
        download_i2v_wan22_models
        ;;
    t2i-qwen)
        download_t2i_qwen_models
        ;;
    t2i-chroma-anime)
        download_t2i_chroma_anime_models
        ;;
    t2i-kids-crayon)
        download_t2i_kids_crayon_models
        ;;
    *)
        echo "No value for COMFYUI_WORKFLOW environment variable. Supported values: i2v-wan22, t2i-qwen, t2i-chroma-anime, t2i-kids-crayon. Defaulting to i2v-wan22." >&2
        download_i2v_wan22_models
        ;;
esac

# Clean up
echo "Cleaning up temporary files..."
apt-get clean
rm -rf /tmp/* /var/tmp/*

echo "Model downloads completed successfully!"
echo "Total model size:"
du -sh /comfyui/models/

echo "Available models:"
find /comfyui/models -type f -name "*.safetensors" -o -name "*.gguf" -o -name "*.pth" | sort
