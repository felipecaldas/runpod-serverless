"""HTTP and websocket client for interacting with the local ComfyUI instance."""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import requests
import websocket
from requests.adapters import HTTPAdapter, Retry

from config import (
    BASE_URI,
    COMFY_API_AVAILABLE_INTERVAL_MS,
    COMFY_API_AVAILABLE_MAX_RETRIES,
    COMFY_HISTORY_ATTEMPTS,
    COMFY_HISTORY_DELAY_SECONDS,
    TIMEOUT,
)
from logging_utils import debug_log_websocket, log_with_job


class ComfyClient:
    """Client encapsulating all network interactions with ComfyUI."""

    def __init__(self) -> None:
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def check_server(self) -> bool:
        """Return True when the ComfyUI REST endpoint is reachable."""
        logging.info("Checking ComfyUI server at %s", BASE_URI)

        for _ in range(COMFY_API_AVAILABLE_MAX_RETRIES):
            try:
                response = self.session.get(BASE_URI, timeout=5)
            except requests.RequestException:
                response = None

            if response and response.status_code == 200:
                logging.info("ComfyUI server is reachable")
                return True

            time.sleep(COMFY_API_AVAILABLE_INTERVAL_MS / 1000)

        logging.error(
            "Failed to connect to ComfyUI server after %s attempts",
            COMFY_API_AVAILABLE_MAX_RETRIES,
        )
        return False

    def send_get(self, endpoint: str) -> requests.Response:
        return self.session.get(f"{BASE_URI}/{endpoint}", timeout=TIMEOUT)

    def send_post(self, endpoint: str, payload: Dict[str, Any]) -> requests.Response:
        return self.session.post(f"{BASE_URI}/{endpoint}", json=payload, timeout=TIMEOUT)

    def upload_image(self, filename: str, file_path: str) -> None:
        with open(file_path, "rb") as file_handle:
            files = {"image": (filename, file_handle, "image/png"), "overwrite": (None, "true")}
            response = self.session.post(f"{BASE_URI}/upload/image", files=files, timeout=30)
            response.raise_for_status()

    def get_output_file_data(self, filename: str, subfolder: str, file_type: str) -> bytes:
        params = {"filename": filename, "subfolder": subfolder, "type": file_type}
        response = self.session.get(f"{BASE_URI}/view", params=params, timeout=30)
        response.raise_for_status()
        return response.content

    def fetch_history(self, prompt_id: str, job_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        for attempt in range(COMFY_HISTORY_ATTEMPTS):
            try:
                response = self.send_get(f"history/{prompt_id}")
            except Exception as exc:  # pragma: no cover - network exceptions logged upstream
                log_with_job(
                    logging.error,
                    f"History fetch failed ({attempt + 1}/{COMFY_HISTORY_ATTEMPTS}): {exc}",
                    job_id,
                )
            else:
                if response.status_code == 200:
                    try:
                        history = response.json()
                    except json.JSONDecodeError as exc:
                        log_with_job(logging.error, f"Invalid history JSON: {exc}", job_id)
                    else:
                        if prompt_id in history:
                            return history[prompt_id]

            if attempt < COMFY_HISTORY_ATTEMPTS - 1:
                log_with_job(
                    logging.debug,
                    f"History not ready for prompt {prompt_id} (attempt {attempt + 1}/{COMFY_HISTORY_ATTEMPTS}), retrying...",
                    job_id,
                )
                time.sleep(COMFY_HISTORY_DELAY_SECONDS)

        return None

    def monitor_prompt(self, prompt_id: str, job_id: str) -> Dict[str, Any]:
        client_id = str(uuid.uuid4())
        ws_url = f"ws://127.0.0.1:8188/ws?clientId={client_id}"

        try:
            ws = websocket.WebSocket()
            ws.connect(ws_url)
            logging.info("Connected to ComfyUI websocket for job %s", job_id)

            while True:
                try:
                    message = ws.recv()
                    debug_log_websocket(message, job_id)
                    data = json.loads(message)
                    websocket_result = self._handle_websocket_message(data, prompt_id, job_id)
                    if websocket_result is True:
                        break
                    if isinstance(websocket_result, dict):
                        return websocket_result
                except websocket.WebSocketTimeoutException:
                    log_with_job(logging.debug, "Websocket receive timed out, continuing...", job_id)
                    continue
                except websocket.WebSocketConnectionClosedException:
                    if not self._attempt_reconnect(ws, ws_url, job_id):
                        return {"error": "Websocket connection lost"}
            ws.close()
        except Exception as exc:
            log_with_job(logging.error, f"Websocket monitoring error: {exc}", job_id)
            fallback = self.fetch_history(prompt_id, job_id)
            if fallback is not None:
                return fallback
            return {"error": f"Monitoring error: {exc}"}

        history = self.fetch_history(prompt_id, job_id)
        if history is None:
            return {
                "error": f"No history found for completed prompt: {prompt_id} after {COMFY_HISTORY_ATTEMPTS} attempts"
            }
        return history

    def _handle_websocket_message(self, data: Dict[str, Any], prompt_id: str, job_id: str) -> bool:
        message_type = data.get("type")
        content = data.get("data", {})

        if message_type == "executing" and content.get("prompt_id") == prompt_id:
            node = content.get("node")
            if not node:
                log_with_job(logging.info, f"Workflow completed for prompt: {prompt_id}", job_id)
                return True
            log_with_job(logging.debug, f"Executing node: {node}", job_id)
        elif message_type == "execution_end" and content.get("prompt_id") == prompt_id:
            log_with_job(logging.info, f"Workflow completed for prompt: {prompt_id}", job_id)
            return True
        elif message_type == "progress_state" and content.get("prompt_id") == prompt_id:
            nodes = content.get("nodes", {})
            if nodes and all(node.get("state") == "finished" for node in nodes.values()):
                log_with_job(logging.info, f"Workflow completed for prompt: {prompt_id}", job_id)
                return True
        elif message_type == "execution_error" and content.get("prompt_id") == prompt_id:
            error_details = (
                f"Node Type: {content.get('node_type')}, Node ID: {content.get('node_id')}, "
                f"Message: {content.get('exception_message')}"
            )
            log_with_job(logging.error, f"Workflow execution error: {error_details}", job_id)
            return {"error": f"Workflow execution error: {error_details}"}

        return False

    def _attempt_reconnect(self, ws: websocket.WebSocket, ws_url: str, job_id: str) -> bool:
        from config import WEBSOCKET_RECONNECT_ATTEMPTS, WEBSOCKET_RECONNECT_DELAY_S

        log_with_job(logging.warning, "Websocket connection closed, attempting to reconnect...", job_id)
        for attempt in range(WEBSOCKET_RECONNECT_ATTEMPTS):
            try:
                ws.connect(ws_url)
                log_with_job(logging.info, "Websocket reconnected successfully", job_id)
                return True
            except Exception as exc:  # pragma: no cover - best-effort reconnect
                log_with_job(logging.error, f"Failed to reconnect websocket: {exc}", job_id)
                time.sleep(WEBSOCKET_RECONNECT_DELAY_S)
        return False
