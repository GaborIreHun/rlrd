import os
import platform
import subprocess
import sys
import torch
import psutil
import pkg_resources
import datetime

OUTPUT = "system_info.txt"

def get_gpu_info():
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_memory // (1024 ** 2)
        return f"{gpu_name} ({gpu_mem} MB VRAM)"
    return "CPU-only (no CUDA available)"

def get_blas_backend():
    try:
        return torch.__config__.show().split("\n")
    except:
        return "Unknown"

def write_section(header, lines):
    with open(OUTPUT, "a") as f:
        f.write(f"\n=== {header} ===\n")
        if isinstance(lines, list):
            f.writelines([line + "\n" for line in lines])
        else:
            f.write(str(lines) + "\n")

# === Start Report ===
with open(OUTPUT, "w") as f:
    f.write("System Information Report\n")
    f.write("=========================\n")
    f.write(f"Generated on: {datetime.datetime.now()}\n")

# OS and Kernel
write_section("OS & Kernel", [
    f"System: {platform.system()} {platform.release()}",
    f"Kernel: {platform.version()}",
    f"Architecture: {platform.machine()}",
])

# CPU & RAM
write_section("CPU & Memory", [
    f"Processor: {platform.processor()}",
    f"Cores: {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count(logical=True)} logical",
    f"RAM: {round(psutil.virtual_memory().total / (1024 ** 3), 2)} GB",
])

# GPU
write_section("GPU", get_gpu_info())

# Python & Libraries
write_section("Python & Libraries", [
    f"Python: {platform.python_version()}",
    f"PyTorch: {torch.__version__}",
    f"CUDA: {torch.version.cuda if torch.cuda.is_available() else 'N/A'}",
    f"cuDNN: {torch.backends.cudnn.version() if torch.cuda.is_available() else 'N/A'}",
])

# Gym, rtrl, rlrd
def get_pkg_version(pkg_name):
    try:
        return pkg_resources.get_distribution(pkg_name).version
    except:
        return "Not installed"

write_section("RL Libraries", [
    f"Gym: {get_pkg_version('gym')}",
    f"Gymnasium: {get_pkg_version('gymnasium')}",
    f"rtrl: {get_pkg_version('rtrl')}",
    f"rlrd: {get_pkg_version('rlrd')}",
    f"wandb: {get_pkg_version('wandb')}",
])

# BLAS backend
write_section("BLAS Backend", get_blas_backend())

# Optionally list installed packages
# write_section("Installed Python Packages", sorted([str(d) for d in pkg_resources.working_set]))

print(f"\n✅ System info written to {OUTPUT}")

