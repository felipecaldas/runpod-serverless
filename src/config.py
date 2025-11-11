"""Central configuration for the RunPod-ComfyUI worker."""
from __future__ import annotations

import os

APP_NAME = "runpod-serverless-comfyui"
BASE_URI = "http://127.0.0.1:8188"
LOG_FILE = "comfyui-worker.log"
TIMEOUT = 600
LOG_LEVEL = os.getenv("COMFY_LOG_LEVEL", "INFO")
DISK_MIN_FREE_BYTES = 500 * 1024 * 1024  # 500MB
COMFY_API_AVAILABLE_INTERVAL_MS = 50
COMFY_API_AVAILABLE_MAX_RETRIES = 500
WEBSOCKET_RECONNECT_ATTEMPTS = int(os.environ.get("WEBSOCKET_RECONNECT_ATTEMPTS", 5))
WEBSOCKET_RECONNECT_DELAY_S = int(os.environ.get("WEBSOCKET_RECONNECT_DELAY_S", 3))
WS_DEBUG_FILE = os.environ.get("COMFY_WS_DEBUG_FILE", "/comfyui/ws.log")
COMFY_HISTORY_ATTEMPTS = int(os.environ.get("COMFY_HISTORY_ATTEMPTS", 120))
COMFY_HISTORY_DELAY_SECONDS = float(os.environ.get("COMFY_HISTORY_DELAY_SECONDS", 2))
