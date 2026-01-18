#!/bin/bash

# Model download script for RunPod serverless ComfyUI worker
# Downloads required models based on models_urls.csv if they don't exist on disk

# Usage:
# 1. Optionally, set the CIVITAI_API_KEY environment variable for Civitai downloads
#    Example: export CIVITAI_API_KEY=your_civitai_api_key_here
#    You can obtain your Civitai API key from https://civitai.com/user/account (API Keys section)
#    If a model requires the API key but it's not set, the download will fail (and continue) for that model.
#
# 2. Run the script: ./download_models.sh
#
# The script will:
# - Determine the models directory (/runpod-volume/comfyui/models or /workspace/comfyui/models)
# - Read all models from models_urls.csv
# - For each model, check if it exists; if not, download it
# - Handle retries and clean up after completion

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

# Determine models directory
if [ -d "/runpod-volume/comfyui/models" ]; then
    MODELS_DIR="/runpod-volume/comfyui/models"
elif [ -d "/workspace/comfyui/models" ]; then
    MODELS_DIR="/workspace/comfyui/models"
else
    echo "Models directory not found" >&2
    exit 1
fi

echo "Using models directory: $MODELS_DIR"

# Read CSV file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CSV_FILE="$SCRIPT_DIR/models_urls.csv"

if [[ ! -f "$CSV_FILE" ]]; then
    echo "CSV file not found: $CSV_FILE" >&2
    exit 1
fi

# Skip header and process each line
tail -n +2 "$CSV_FILE" | while IFS= read -r line; do
    if [[ -z "$line" ]]; then
        continue
    fi

    model=$(echo "$line" | cut -d, -f1)
    folder=$(echo "$line" | cut -d, -f2)
    url=$(echo "$line" | cut -d, -f3-)

    # Check if Civitai download and API key not set
    if [[ "$url" == *civitai.com* && -z "${CIVITAI_API_KEY:-}" ]]; then
        echo "Skipping $model: CIVITAI_API_KEY not set"
        continue
    fi

    # Replace token placeholder
    url="${url/\$\{CIVITAI_API_KEY\}/${CIVITAI_API_KEY:-}}"

    model_path="$MODELS_DIR/$folder/$model"

    if [[ -f "$model_path" ]]; then
        echo "Model $model already exists at $model_path"
    else
        echo "Downloading $model to $model_path"
        if ! download_with_retry "$url" "$model_path"; then
            echo "Failed to download $model" >&2
            exit 1
        fi
    fi
done

# Clean up
echo "Cleaning up temporary files..."
apt-get clean
rm -rf /tmp/* /var/tmp/*

echo "Model downloads completed successfully!"
echo "Total model size:"
du -sh $MODELS_DIR
