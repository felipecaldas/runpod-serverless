"""Unit tests for RunPod input schema validation."""

from __future__ import annotations

import pytest

runpod = pytest.importorskip("runpod")

from runpod.serverless.utils.rp_validator import validate

from input_schema import INPUT_SCHEMA


def test_validate_input_schema_allows_missing_output_resolution() -> None:
    payload = {
        "prompt": "hello",
        "width": 512,
        "height": 768,
        "comfyui_workflow_name": "image_disneyizt_t2i",
    }

    result = validate(payload, INPUT_SCHEMA)

    assert "errors" not in result
    validated = result["validated_input"]
    assert validated["output_resolution"] is None


def test_validate_input_schema_allows_missing_comfy_org_api_key() -> None:
    payload = {
        "prompt": "hello",
        "width": 512,
        "height": 768,
    }

    result = validate(payload, INPUT_SCHEMA)

    assert "errors" not in result
    validated = result["validated_input"]
    assert validated["comfy_org_api_key"] == ""


def test_validate_input_schema_allows_missing_image_style() -> None:
    payload = {
        "prompt": "hello",
        "width": 512,
        "height": 768,
    }

    result = validate(payload, INPUT_SCHEMA)

    assert "errors" not in result
    validated = result["validated_input"]
    assert validated["image_style"] is None


def test_validate_input_schema_accepts_valid_image_style() -> None:
    payload = {
        "prompt": "hello",
        "image_style": "Film Noir",
    }

    result = validate(payload, INPUT_SCHEMA)

    assert "errors" not in result
    validated = result["validated_input"]
    assert validated["image_style"] == "Film Noir"


def test_validate_input_schema_accepts_normalized_street_documentary_style() -> None:
    payload = {
        "prompt": "hello",
        "image_style": "Street Documentary",
    }

    result = validate(payload, INPUT_SCHEMA)

    assert "errors" not in result
    validated = result["validated_input"]
    assert validated["image_style"] == "Street Documentary"


def test_validate_input_schema_rejects_invalid_image_style() -> None:
    payload = {
        "prompt": "hello",
        "image_style": "Not a real style",
    }

    result = validate(payload, INPUT_SCHEMA)

    assert "errors" in result
