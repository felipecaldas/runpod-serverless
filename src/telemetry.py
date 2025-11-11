"""Container telemetry helpers for the RunPod-ComfyUI worker."""
from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from logging_utils import log_with_job


def get_container_memory_info(job_id: Optional[str] = None) -> Dict[str, float]:
    """Return memory statistics in gigabytes gathered from cgroups or host."""
    try:
        mem_info: Dict[str, float] = {}

        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as meminfo_file:
                meminfo_lines = meminfo_file.readlines()

            for line in meminfo_lines:
                if "MemTotal:" in line:
                    mem_info["total"] = int(line.split()[1]) / (1024 * 1024)
                elif "MemAvailable:" in line:
                    mem_info["available"] = int(line.split()[1]) / (1024 * 1024)
                elif "MemFree:" in line:
                    mem_info["free"] = int(line.split()[1]) / (1024 * 1024)

            if "total" in mem_info and "free" in mem_info:
                mem_info["used"] = mem_info["total"] - mem_info["free"]
        except Exception as exc:
            log_with_job(logging.warning, f"Failed to read host memory info: {exc}", job_id)

        try:
            with open("/sys/fs/cgroup/memory.max", "r", encoding="utf-8") as max_file:
                max_value = max_file.read().strip()
                if max_value != "max":
                    mem_info["limit"] = int(max_value) / (1024 * 1024 * 1024)

            with open("/sys/fs/cgroup/memory.current", "r", encoding="utf-8") as current_file:
                mem_info["used"] = int(current_file.read().strip()) / (1024 * 1024 * 1024)
        except FileNotFoundError:
            try:
                with open("/sys/fs/cgroup/memory/memory.limit_in_bytes", "r", encoding="utf-8") as limit_file:
                    mem_limit = int(limit_file.read().strip())
                    if mem_limit < 2**63:
                        mem_info["limit"] = mem_limit / (1024 * 1024 * 1024)

                with open("/sys/fs/cgroup/memory/memory.usage_in_bytes", "r", encoding="utf-8") as usage_file:
                    mem_info["used"] = int(usage_file.read().strip()) / (1024 * 1024 * 1024)
            except FileNotFoundError:
                pass

        return mem_info
    except Exception as exc:
        log_with_job(logging.error, f"Error getting memory info: {exc}", job_id)
        return {}


def get_container_cpu_info(job_id: Optional[str] = None) -> Dict[str, float]:
    """Return CPU quota details derived from cgroups, falling back to host values."""
    try:
        cpu_info: Dict[str, float] = {}

        try:
            with open("/sys/fs/cgroup/cpu.max", "r", encoding="utf-8") as cpu_max_file:
                cpu_max = cpu_max_file.read().strip()
                if cpu_max != "max":
                    quota, period = cpu_max.split()
                    cpu_info["limit"] = int(quota) / int(period)
                else:
                    cpu_info["limit"] = os.cpu_count() or 0

            with open("/sys/fs/cgroup/cpu.stat", "r", encoding="utf-8") as cpu_stat_file:
                for line in cpu_stat_file:
                    if line.startswith("usage_usec "):
                        cpu_info["usage_usec"] = int(line.split()[1])
                        break
        except FileNotFoundError:
            try:
                with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", "r", encoding="utf-8") as quota_file:
                    quota = int(quota_file.read().strip())
                    if quota > 0:
                        with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us", "r", encoding="utf-8") as period_file:
                            period = int(period_file.read().strip())
                            cpu_info["limit"] = quota / period
                    else:
                        cpu_info["limit"] = os.cpu_count() or 0
            except FileNotFoundError:
                cpu_info["limit"] = os.cpu_count() or 0

        return cpu_info
    except Exception as exc:
        log_with_job(logging.error, f"Error getting CPU info: {exc}", job_id)
        return {"limit": float(os.cpu_count() or 0)}


def get_container_disk_info(job_id: Optional[str] = None) -> Dict[str, float]:
    """Return disk usage statistics for the container."""
    try:
        stat = os.statvfs("/")
        total = stat.f_frsize * stat.f_blocks
        free = stat.f_frsize * stat.f_bavail

        return {
            "total": total,
            "free": free,
            "used": total - free,
        }
    except Exception as exc:
        log_with_job(logging.error, f"Error getting disk info: {exc}", job_id)
        return {}
