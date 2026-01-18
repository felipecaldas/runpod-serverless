#!/usr/bin/env python3
"""
Script to generate a RunPod /run request body for video upscaling using SeedVR2.

Reads a video file, encodes it to base64, and outputs the JSON request payload.
"""

import base64
import json
import os
import sys

def encode_video_to_base64(file_path):
    """Encode video file to base64 data URI."""
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(file_path, 'rb') as video_file:
            video_data = video_file.read()
            base64_encoded = base64.b64encode(video_data).decode('utf-8')
            return f"data:video/mp4;base64,{base64_encoded}"
    except Exception as e:
        print(f"Error reading or encoding file: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    video_file = "./final_video.mp4"

    # Encode the video
    video_base64 = encode_video_to_base64(video_file)

    # Build the request payload
    request_body = {
        "input": {
            "video": video_base64,
            "width": 1920,
            "height": 1080,
            "output_resolution": 1920,
            "comfyui_workflow_name": "seedvr2_video_upscale",
            "comfy_org_api_key": "<REPLACE_WITH_YOUR_COMFY_ORG_API_KEY>"
        }
    }

    # Output the JSON to a file
    output_file = "./upscale_request.json"
    with open(output_file, 'w') as f:
        json.dump(request_body, f, indent=2)
    print(f"Request body saved to {output_file}")

if __name__ == "__main__":
    main()
