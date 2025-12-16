"""Utilities for preparing ComfyUI workflows."""
from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import uuid
from io import BytesIO
from typing import Any, Dict, TYPE_CHECKING

from PIL import Image

from logging_utils import log_with_job

if TYPE_CHECKING:
    from comfy_client import ComfyClient


WORKFLOW_TEMPLATES: Dict[str, str] = {
    "video_wan2_2_14B_i2v": "video_wan2_2_14B_i2v.json",
    "T2I_ChromaAnimaAIO": "T2I_ChromaAnimaAIO.json",
    "qwen-image-fast-runpod": "qwen-image-fast-runpod.json",
    "image_qwen_t2i": "image_qwen_image_distill_official_comfyui.json",
    "crayon-drawing": "crayon-drawing.json",
    "I2V-Wan-2.2-Lightning-runpod": "I2V-Wan-2.2-Lightning-runpod.json",
}


def load_workflow_template(workflow_name: str) -> Dict[str, Any]:
    """Load a workflow template from disk."""
    template_file = WORKFLOW_TEMPLATES.get(workflow_name, WORKFLOW_TEMPLATES["video_wan2_2_14B_i2v"])
    template_path = os.path.join(os.path.dirname(__file__), "..", "workflows", template_file)
    try:
        with open(template_path, "r", encoding="utf-8") as template_handle:
            return json.load(template_handle)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Workflow template not found at {template_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in workflow template: {exc}") from exc


def workflow_requires_input_image(workflow: Dict[str, Any]) -> bool:
    """Return True when the workflow template includes an input image placeholder."""

    def _contains(value: Any) -> bool:
        if isinstance(value, dict):
            return any(_contains(item) for item in value.values())
        if isinstance(value, list):
            return any(_contains(item) for item in value)
        return value == "{{ INPUT_IMAGE }}"

    return _contains(workflow)


def upload_input_image(
    image_data_uri: str,
    job_id: str,
    width: int,
    height: int,
    client: "ComfyClient",
) -> str:
    """Decode and upload the input image to ComfyUI, returning the filename."""
    try:
        base64_data = image_data_uri.split(",", 1)[1] if "," in image_data_uri else image_data_uri
        blob = base64.b64decode(base64_data)
        image = Image.open(BytesIO(blob)).convert("RGB")
    except Exception as exc:
        raise ValueError(f"Invalid base64 image data: {exc}") from exc

    if image.size != (width, height):
        log_with_job(
            logging.info,
            f"Resizing input image from {image.size[0]}x{image.size[1]} to {width}x{height}",
            job_id,
        )
        image = image.resize((width, height), Image.LANCZOS)

    filename = f"{uuid.uuid4()}.png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
        image.save(temp_file, format="PNG")
        temp_file_path = temp_file.name

    try:
        client.upload_image(filename, temp_file_path)
        log_with_job(logging.info, f"Successfully uploaded image as {filename}", job_id)
        return filename
    finally:
        os.unlink(temp_file_path)


def prepare_workflow(
    workflow: Dict[str, Any],
    prompt: str,
    image_filename: str,
    width: int,
    height: int,
    length: int,
    job_id: str,
) -> Dict[str, Any]:
    """Prepare a workflow by injecting prompt, image, dimensions, and unique filenames."""
    workflow = substitute_workflow_placeholders(workflow, prompt, image_filename, width, height)

    try:
        set_workflow_dimensions(workflow, width, height, length)
    except ValueError as exc:
        log_with_job(logging.debug, f"Skipping dimension override: {exc}", job_id)

    create_unique_filename_prefix(workflow)
    return workflow


def substitute_workflow_placeholders(
    workflow: Dict[str, Any],
    prompt: str,
    image_filename: str,
    width: int,
    height: int,
) -> Dict[str, Any]:
    """Replace placeholder tokens within the workflow template."""

    def _replace(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: _replace(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_replace(item) for item in value]
        if value == "{{ VIDEO_PROMPT }}":
            return prompt
        if value == "{{ POSITIVE_PROMPT }}":
            return prompt
        if value == "{{ IMAGE_PROMPT }}":
            return prompt
        if value == "{{ INPUT_IMAGE }}":
            return image_filename
        if value == "{{ IMAGE_WIDTH }}":
            return width
        if value == "{{ IMAGE_HEIGHT }}":
            return height
        return value

    return _replace(workflow)


def set_workflow_dimensions(workflow: Dict[str, Any], width: int, height: int, length: int) -> None:
    """Apply dimension overrides to WanImageToVideo nodes."""
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") == "WanImageToVideo":
            inputs = node.setdefault("inputs", {})
            inputs["width"] = width
            inputs["height"] = height
            inputs["length"] = length
            log_with_job(logging.info, f"Set workflow dimensions: {width}x{height}, length={length}", None)
            return

    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") == "EmptySD3LatentImage":
            inputs = node.setdefault("inputs", {})
            inputs["width"] = width
            inputs["height"] = height
            log_with_job(logging.info, f"Set workflow dimensions: {width}x{height}", None)
            return

    raise ValueError("No supported dimension nodes found in workflow template")


def create_unique_filename_prefix(workflow: Dict[str, Any]) -> None:
    """Ensure SaveImage nodes use unique filename prefixes to avoid collisions."""
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") == "SaveImage":
            inputs = node.setdefault("inputs", {})
            inputs["filename_prefix"] = str(uuid.uuid4())
