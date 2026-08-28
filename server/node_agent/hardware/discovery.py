import platform
from dataclasses import dataclass
from typing import Any

import psutil

from .gpu import detect_gpus


@dataclass
class HardwareInfo:
    cpu_model: str
    cpu_cores: int
    ram_gb: int
    storage_gb: int
    os_info: str


def discover_cpu_ram_storage() -> HardwareInfo:
    cpu_model = platform.processor() or "Unknown CPU"
    cpu_cores = psutil.cpu_count(logical=False) or 1
    ram_gb = psutil.virtual_memory().total // (1024**3)
    storage_gb = psutil.disk_usage("/").total // (1024**3)
    os_info = platform.platform()

    return HardwareInfo(cpu_model=cpu_model, cpu_cores=cpu_cores, ram_gb=ram_gb, storage_gb=storage_gb, os_info=os_info)


def discover_all() -> dict[str, Any]:
    hw = discover_cpu_ram_storage()
    gpu = detect_gpus()

    return {
        "cpu_model": hw.cpu_model,
        "cpu_cores": hw.cpu_cores,
        "ram_gb": hw.ram_gb,
        "storage_gb": hw.storage_gb,
        "os_info": hw.os_info,
        "gpu_model": gpu.model,
        "gpu_count": gpu.count,
        "gpu_vram_gb": gpu.vram_gb,
        "capabilities": ["cpu", "gpu"] if gpu.count > 0 else ["cpu"],
    }
