"""Processing utilities for ComfyUI workflow outputs."""
from __future__ import annotations

import base64
import logging
import os
import tempfile
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from comfy_client import ComfyClient


class OutputProcessor:
    """Handle retrieval and serialization of ComfyUI workflow assets."""

    def __init__(self, client: "ComfyClient") -> None:
        self._client = client

    def process(self, outputs: Dict[str, Any], job_id: str) -> Dict[str, List[Dict[str, str]]]:
        result: Dict[str, List[Dict[str, str]]] = {"images": [], "videos": []}

        for node_output in outputs.values():
            self._collect_assets(node_output, result, job_id)

        total_assets = len(result["images"]) + len(result["videos"])
        logging.info(
            "Processed workflow outputs: %s assets (images=%s, videos=%s)",
            total_assets,
            len(result["images"]),
            len(result["videos"]),
        )
        return result

    def _collect_assets(
        self,
        node_output: Dict[str, Any],
        buckets: Dict[str, List[Dict[str, str]]],
        job_id: str,
    ) -> None:
        collections = {
            key: node_output.get(key, [])
            for key in ("images", "videos")
        }

        for entries in collections.values():
            if not isinstance(entries, list):
                continue

            for asset_info in entries:
                filename = asset_info.get("filename")
                subfolder = asset_info.get("subfolder", "")
                asset_type = asset_info.get("type", "output")

                if not filename or asset_type == "temp":
                    continue

                bucket_key = self._resolve_bucket(filename)
                asset_bytes = self._client.get_output_file_data(filename, subfolder, asset_type)

                if os.environ.get("BUCKET_ENDPOINT_URL"):
                    buckets[bucket_key].append({
                        "filename": filename,
                        "type": "s3_url",
                        "data": self._upload_to_s3(asset_bytes, filename, job_id),
                    })
                else:
                    buckets[bucket_key].append({
                        "filename": filename,
                        "type": "base64",
                        "data": base64.b64encode(asset_bytes).decode("utf-8"),
                    })

    @staticmethod
    def _resolve_bucket(filename: str) -> str:
        _, ext = os.path.splitext(filename.lower())
        if ext in {".mp4", ".mov", ".webm", ".mkv", ".avi"}:
            return "videos"
        return "images"

    def _upload_to_s3(self, data: bytes, filename: str, job_id: str) -> str:
        try:
            from runpod.serverless.utils import rp_upload
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("RunPod upload utility is not available") from exc

        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1] or ".bin") as temp_file:
            temp_file.write(data)
            temp_path = temp_file.name

        try:
            s3_url = rp_upload.upload_image(job_id, temp_path)
            logging.info("Uploaded %s to S3: %s", filename, s3_url)
            return s3_url
        finally:
            os.unlink(temp_path)

    def get_output_summary(self, outputs: Dict[str, Any]) -> str:
        image_count = sum(len(node.get("images", [])) for node in outputs.values())
        video_count = sum(len(node.get("videos", [])) for node in outputs.values())
        return f"images={image_count}, videos={video_count}"
