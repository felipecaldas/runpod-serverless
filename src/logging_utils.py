"""Logging utilities for the RunPod-ComfyUI worker."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional

import os
import requests
from runpod.serverless.modules.rp_logger import RunPodLogger

from config import APP_NAME, LOG_LEVEL, WS_DEBUG_FILE


def log_with_job(level_func: Callable[[str], None], message: str, job_id: Optional[str]) -> None:
    """Log a message, appending the RunPod job ID when present."""
    if job_id:
        level_func(f"{message} | job_id={job_id}")
        return

    level_func(message)


def debug_log_websocket(message: str, job_id: Optional[str]) -> None:
    """Write websocket payloads to the configured debug file when enabled."""
    if not WS_DEBUG_FILE:
        return

    try:
        timestamp = datetime.utcnow().isoformat()
        with open(WS_DEBUG_FILE, "a", encoding="utf-8") as debug_file:
            if job_id:
                debug_file.write(f"{timestamp} | job_id={job_id} | {message}\n")
            else:
                debug_file.write(f"{timestamp} | {message}\n")
    except Exception as exc:  # pragma: no cover - best-effort debug logging
        logging.error("Failed to write websocket debug log: %s", exc)


class SnapLogHandler(logging.Handler):
    """Custom log handler that forwards logs to RunPod telemetry and optional HTTP endpoint."""

    def __init__(self, app_name: str = APP_NAME) -> None:
        super().__init__()
        self.app_name = app_name
        self.rp_logger = RunPodLogger()
        self.rp_logger.set_level(LOG_LEVEL)

        # RunPod environment metadata
        self.runpod_endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")
        self.runpod_cpu_count = os.getenv("RUNPOD_CPU_COUNT")
        self.runpod_pod_id = os.getenv("RUNPOD_POD_ID")
        self.runpod_gpu_size = os.getenv("RUNPOD_GPU_SIZE")
        self.runpod_mem_gb = os.getenv("RUNPOD_MEM_GB")
        self.runpod_gpu_count = os.getenv("RUNPOD_GPU_COUNT")
        self.runpod_pod_hostname = os.getenv("RUNPOD_POD_HOSTNAME")
        self.runpod_debug_level = os.getenv("RUNPOD_DEBUG_LEVEL")
        self.runpod_dc_id = os.getenv("RUNPOD_DC_ID")
        self.runpod_gpu_name = os.getenv("RUNPOD_GPU_NAME")

        # Optional external logging endpoint
        self.log_api_endpoint = os.getenv("LOG_API_ENDPOINT")
        self.log_api_timeout = int(os.getenv("LOG_API_TIMEOUT", "5"))
        self.log_token = os.getenv("LOG_API_TOKEN")

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - logging integration
        """Emit a log record to RunPod's logger and, optionally, an external HTTP endpoint."""
        runpod_job_id = os.getenv("RUNPOD_JOB_ID")

        try:
            message = self._format_message(record)
            self._emit_runpod_log(record.levelno, message, runpod_job_id)
            self._emit_external_log(record, message, runpod_job_id)
        except Exception as exc:
            print(f"Logging error: {exc}")

    def _format_message(self, record: logging.LogRecord) -> str:
        if record.args:
            try:
                return record.msg % record.args
            except (TypeError, ValueError):
                return str(record.msg)
        return str(record.msg)

    def _emit_runpod_log(self, levelno: int, message: str, job_id: Optional[str]) -> None:
        if len(message) > 1000:
            return

        level_mapping = {
            logging.DEBUG: self.rp_logger.debug,
            logging.INFO: self.rp_logger.info,
            logging.WARNING: self.rp_logger.warn,
            logging.ERROR: self.rp_logger.error,
            logging.CRITICAL: self.rp_logger.error,
        }
        rp_logger = level_mapping.get(levelno, self.rp_logger.info)

        if job_id:
            rp_logger(message, job_id)
            return

        rp_logger(message)

    def _emit_external_log(self, record: logging.LogRecord, message: str, job_id: Optional[str]) -> None:
        if not self.log_api_endpoint:
            return

        payload = {
            "app_name": self.app_name,
            "log_asctime": self.formatter.formatTime(record),
            "log_levelname": record.levelname,
            "log_message": message,
            "runpod_endpoint_id": self.runpod_endpoint_id,
            "runpod_pod_id": self.runpod_pod_id,
            "runpod_job_id": job_id,
            "runpod_gpu_size": self.runpod_gpu_size,
            "runpod_mem_gb": self.runpod_mem_gb,
            "runpod_gpu_count": self.runpod_gpu_count,
            "runpod_gpu_name": self.runpod_gpu_name,
            "runpod_pod_hostname": self.runpod_pod_hostname,
        }

        headers = {"Authorization": f"Bearer {self.log_token}"} if self.log_token else None

        try:
            requests.post(
                self.log_api_endpoint,
                headers=headers,
                json=payload,
                timeout=self.log_api_timeout,
            )
        except Exception as exc:
            print(f"Failed to send log to external API: {exc}")


def setup_logging(app_name: str = APP_NAME) -> logging.Logger:
    """Initialize logging for the worker and return the configured logger."""
    logger = logging.getLogger(app_name)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    custom_handler = SnapLogHandler(app_name)
    custom_handler.setFormatter(formatter)
    logger.addHandler(custom_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
