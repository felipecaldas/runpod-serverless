"""Unit tests for handling temp video outputs from ComfyUI history."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from outputs import OutputProcessor


class _StubComfyClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def get_output_file_data(self, filename: str, subfolder: str, file_type: str) -> bytes:
        self.calls.append((filename, subfolder, file_type))
        if file_type == "output":
            return b"mp4-bytes"
        raise RuntimeError("not found")


def test_process_includes_temp_video_assets() -> None:
    client = _StubComfyClient()
    processor = OutputProcessor(client)  # type: ignore[arg-type]

    outputs: Dict[str, Any] = {
        "5": {
            "videos": [
                {
                    "filename": "seedvr2_upscaled_00001.mp4",
                    "subfolder": "",
                    "type": "temp",
                }
            ]
        }
    }

    result = processor.process(outputs, job_id="job")

    assert len(result["videos"]) == 1
    assert result["videos"][0]["filename"] == "seedvr2_upscaled_00001.mp4"
    assert result["videos"][0]["type"] == "base64"
    assert result["videos"][0]["data"]
    assert client.calls[0] == ("seedvr2_upscaled_00001.mp4", "", "output")


def test_process_skips_temp_images() -> None:
    client = _StubComfyClient()
    processor = OutputProcessor(client)  # type: ignore[arg-type]

    outputs: Dict[str, Any] = {
        "7": {
            "images": [
                {
                    "filename": "frame_00001.png",
                    "subfolder": "",
                    "type": "temp",
                }
            ]
        }
    }

    result = processor.process(outputs, job_id="job")

    assert result["images"] == []
    assert client.calls == []


def test_process_treats_gifs_mp4_as_video() -> None:
    client = _StubComfyClient()
    processor = OutputProcessor(client)  # type: ignore[arg-type]

    outputs: Dict[str, Any] = {
        "5": {
            "gifs": [
                {
                    "filename": "seedvr2_upscaled_00001.mp4",
                    "subfolder": "",
                    "type": "output",
                }
            ]
        }
    }

    result = processor.process(outputs, job_id="job")

    assert len(result["videos"]) == 1
    assert result["videos"][0]["filename"] == "seedvr2_upscaled_00001.mp4"
