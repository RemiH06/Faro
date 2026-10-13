# Crea el entorno de Faro en un equipo Windows con GPU NVIDIA. Se corre una vez desde la raíz del repo:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\preparar_windows_gpu.ps1
# No necesita el CUDA Toolkit: el wheel de PyTorch trae su runtime, y transcribir.py lo reutiliza.
$ErrorActionPreference = "Stop"
if (-not (Test-Path .venv)) { python -m venv .venv }
$py = ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
& $py -m pip install -r requirements.txt
& $py -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
