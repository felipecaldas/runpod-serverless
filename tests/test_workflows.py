"""Unit tests for workflow preparation utilities."""
from __future__ import annotations

import json

from workflows import create_unique_filename_prefix, set_workflow_dimensions, substitute_workflow_placeholders


def test_substitute_workflow_placeholders() -> None:
    template = {"1": {"prompt": "{{ VIDEO_PROMPT }}", "image": "{{ INPUT_IMAGE }}"}}
    result = substitute_workflow_placeholders(template, "hello", "image.png")

    assert result["1"]["prompt"] == "hello"
    assert result["1"]["image"] == "image.png"


def test_set_workflow_dimensions_sets_values() -> None:
    template = {
        "1": {
            "class_type": "WanImageToVideo",
            "inputs": {"width": 0, "height": 0, "length": 0},
        }
    }

    set_workflow_dimensions(template, 480, 640, 81)

    inputs = template["1"]["inputs"]
    assert inputs["width"] == 480
    assert inputs["height"] == 640
    assert inputs["length"] == 81


def test_create_unique_filename_prefix_generates_uuid() -> None:
    template = {"1": {"class_type": "SaveImage", "inputs": {}}}

    create_unique_filename_prefix(template)

    prefix = template["1"]["inputs"]["filename_prefix"]
    assert isinstance(prefix, str)
    assert len(prefix) > 0
