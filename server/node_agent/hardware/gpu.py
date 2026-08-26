import subprocess
from dataclasses import dataclass

@dataclass
class GPUInfo:
    model: str
    count: int
    vram_gb: int
    vendor: str

def detect_nvidia_gpus() -> GPUInfo:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,count", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True
        )
        lines = result.stdout.strip().split('\n')
        if not lines or not lines[0]:
            return None
            
        first_gpu = lines[0].split(',')
        model = first_gpu[0].strip()
        vram_mb = int(first_gpu[1].strip())
        count = len(lines)
        
        return GPUInfo(
            model=model,
            count=count,
            vram_gb=vram_mb // 1024,
            vendor="NVIDIA"
        )
    except (subprocess.SubprocessError, FileNotFoundError, ValueError):
        return None

def detect_gpus() -> GPUInfo:
    nvidia = detect_nvidia_gpus()
    if nvidia:
        return nvidia
        
    return GPUInfo(
        model="No GPU detected",
        count=0,
        vram_gb=0,
        vendor="None"
    )
