"""Input schema for RunPod serverless worker validation."""

from __future__ import annotations

from typing import Any, Dict

INPUT_SCHEMA: Dict[str, Any] = {
    "prompt": {
        "type": str,
        "required": False,
        "default": "",
        "constraints": lambda prompt: prompt in (None, "") or (isinstance(prompt, str) and len(prompt) > 0),
    },
    "image": {
        "type": str,
        "required": False,
        "default": "",
        "constraints": lambda image: image in (None, "") or (isinstance(image, str) and len(image) > 0),
    },
    "width": {"type": int, "required": False, "default": 480},
    "height": {"type": int, "required": False, "default": 640},
    "length": {"type": int, "required": False, "default": 81},
    "comfyui_workflow_name": {
        "type": str,
        "required": False,
        "default": "video_wan2_2_14B_i2v",
    },
    "video": {
        "type": str,
        "required": False,
        "default": "",
        "constraints": lambda video: video in (None, "") or (isinstance(video, str) and len(video) > 0),
    },
    "frame_rate": {"type": int, "required": False, "default": 24},
    "output_resolution": {
        "type": (int, type(None)),
        "required": False,
        "default": None,
        "constraints": lambda value: value is None or (isinstance(value, int) and value > 0),
    },
    "comfy_org_api_key": {"type": str, "required": False, "default": ""},
    "batch_size": {"type": int, "required": False, "default": 29},
}
