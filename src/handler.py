"""RunPod serverless worker handler orchestrating ComfyUI requests."""
from __future__ import annotations

import logging
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import runpod
import torch
from runpod.serverless.utils.rp_validator import validate

from comfy_client import ComfyClient
from config import (
    APP_NAME,
    COMFY_HISTORY_ATTEMPTS,
    COMFY_HISTORY_DELAY_SECONDS,
    DISK_MIN_FREE_BYTES,
)
from logging_utils import log_with_job, setup_logging
from outputs import OutputProcessor
from telemetry import get_container_disk_info, get_container_memory_info
from workflows import load_workflow_template, prepare_workflow, upload_input_image, workflow_requires_input_image

torch.backends.cuda.enable_flash_sdp(False)
torch.backends.cuda.matmul.allow_tf32 = True
torch.set_float32_matmul_precision("medium")


INPUT_SCHEMA: Dict[str, Any] = {
    "prompt": {
        "type": str,
        "required": True,
        "constraints": lambda prompt: isinstance(prompt, str) and len(prompt) > 0,
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
    "comfy_org_api_key": {"type": str, "required": False},
}


client = ComfyClient()
output_processor = OutputProcessor(client)


def handler(event: Dict[str, Any]) -> Dict[str, Any]:
    """RunPod entrypoint that validates input, executes the workflow, and returns assets."""

    job_id = event["id"]
    os.environ["RUNPOD_JOB_ID"] = job_id

    try:
        log_with_job(logging.info, "Starting job", job_id)

        if not _check_resources(job_id):
            return {
                "error": "Insufficient resources to start the job. See logs for details.",
            }

        validated_input = validate(event["input"], INPUT_SCHEMA)
        if "errors" in validated_input:
            return {"error": "\n".join(validated_input["errors"])}

        job_input = validated_input["validated_input"]
        prompt = job_input["prompt"]
        image_b64 = job_input.get("image")
        width = job_input.get("width", 480)
        height = job_input.get("height", 640)
        length = job_input.get("length", 81)
        workflow_name = job_input.get("comfyui_workflow_name", "video_wan2_2_14B_i2v")
        comfy_org_api_key = job_input.get("comfy_org_api_key")

        log_with_job(
            logging.info,
            f"Processing workflow '{workflow_name}' with prompt '{prompt[:50]}...'",
            job_id,
        )

        if comfy_org_api_key:
            os.environ["COMFY_ORG_API_KEY"] = comfy_org_api_key

        if not client.check_server():
            raise RuntimeError("ComfyUI server is not ready")

        log_with_job(logging.info, "Loading workflow template", job_id)
        workflow_template = load_workflow_template(workflow_name)

        uploaded_filename = ""
        if workflow_requires_input_image(workflow_template):
            if not image_b64:
                return {"error": "'image' is required for this workflow."}

            log_with_job(logging.info, "Uploading input image to ComfyUI", job_id)
            uploaded_filename = upload_input_image(image_b64, job_id, width, height, client)
        workflow = prepare_workflow(
            workflow_template,
            prompt,
            uploaded_filename,
            width,
            height,
            length,
            job_id,
        )

        log_with_job(logging.info, "Submitting workflow to ComfyUI", job_id)
        response = client.send_post("prompt", {"prompt": workflow})

        if response.status_code != 200:
            raise RuntimeError(f"Failed to queue workflow: {response.text}")

        prompt_id = response.json().get("prompt_id")
        log_with_job(logging.info, f"Workflow queued successfully: {prompt_id}", job_id)

        result = client.monitor_prompt(prompt_id, job_id)
        if "error" in result:
            fallback = client.fetch_history(prompt_id, job_id)
            if fallback is not None:
                result = fallback
            else:
                return result

        result = _ensure_final_assets(result, prompt_id, client, job_id)

        outputs = result.get("outputs", {})
        if not outputs:
            log_with_job(logging.warning, f"No outputs found for prompt {prompt_id}", job_id)
            return {"output": {"images": [], "videos": []}}

        workflow_outputs = output_processor.process(outputs, job_id)
        log_with_job(
            logging.info,
            f"Processed workflow outputs for prompt {prompt_id}: "
            f"images={len(workflow_outputs['images'])}, videos={len(workflow_outputs['videos'])}",
            job_id,
        )

        return {"output": workflow_outputs}

    except Exception as exc:
        error_msg = f"Handler error: {exc}"
        log_with_job(logging.error, error_msg, job_id)
        log_with_job(logging.error, traceback.format_exc(), job_id)
        return {"error": error_msg}


def _ensure_final_assets(
    result: Dict[str, Any],
    prompt_id: str,
    client: ComfyClient,
    job_id: str,
) -> Dict[str, Any]:
    """Poll ComfyUI history until workflow assets are finalized or retries are exhausted."""

    if _has_final_assets(result):
        return result

    log_with_job(logging.info, "Waiting for workflow assets to finalize", job_id)
    latest_result = result

    for attempt in range(COMFY_HISTORY_ATTEMPTS):
        time.sleep(COMFY_HISTORY_DELAY_SECONDS)
        refreshed = client.fetch_history(prompt_id, job_id)
        if refreshed is None:
            continue

        latest_result = refreshed
        if _has_final_assets(refreshed):
            log_with_job(
                logging.info,
                f"Workflow assets finalized after {attempt + 1} refresh attempt(s)",
                job_id,
            )
            return refreshed

    log_with_job(
        logging.warning,
        "Workflow assets did not finalize within the allotted retries; proceeding with available data",
        job_id,
    )
    return latest_result


def _has_final_assets(result: Dict[str, Any]) -> bool:
    """Return True when the history payload contains at least one non-temporary asset."""

    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        return False

    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue

        for collection in ("images", "videos"):
            entries = node_output.get(collection, [])
            if not isinstance(entries, list):
                continue

            for asset_info in entries:
                if not isinstance(asset_info, dict):
                    continue

                if asset_info.get("type", "output") != "temp":
                    return True

    return False


def _check_resources(job_id: str) -> bool:
    memory_info = get_container_memory_info(job_id)
    disk_info = get_container_disk_info(job_id)

    memory_available_gb = memory_info.get("available")
    disk_free_bytes = disk_info.get("free")

    if memory_available_gb is not None and memory_available_gb < 0.5:
        log_with_job(
            logging.error,
            f"Insufficient available container memory: {memory_available_gb:.2f} GB available",
            job_id,
        )
        return False

    if disk_free_bytes is not None and disk_free_bytes < DISK_MIN_FREE_BYTES:
        free_gb = disk_free_bytes / (1024 ** 3)
        log_with_job(
            logging.error,
            f"Insufficient free container disk space: {free_gb:.2f} GB available",
            job_id,
        )
        return False

    return True


logger = setup_logging(APP_NAME)


if __name__ == "__main__":
    logger.info("Worker initialization started")
    logger.info("Starting RunPod serverless worker")
    runpod.serverless.start({"handler": handler})
