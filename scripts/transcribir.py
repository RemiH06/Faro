"""Transcribe el audio de los videos de un caso con faster-whisper, en local.

Deja trabajo/<video>/transcripcion.txt con marcas [mm:ss]. Salta los que ya tienen
transcripción. El audio se decodifica con ffmpeg (no con PyAV, que choca con
faster-whisper 1.2 en versiones nuevas).

Uso:
  python scripts/transcribir.py <caso> [video ...] [--modelo small] [--dispositivo auto|cpu|cuda]
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))  # con python -I no se agrega solo
from config import carpeta_casos  # noqa: E402

RAIZ = carpeta_casos()
VIDEO = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}


def ffmpeg_exe() -> str:
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    import imageio_ffmpeg  # equipos sin ffmpeg en el sistema: usa el que trae el paquete

    return imageio_ffmpeg.get_ffmpeg_exe()


def audio(video: Path) -> np.ndarray:
    raw = subprocess.run([ffmpeg_exe(), "-v", "error", "-i", str(video), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def dlls_cuda_de_torch() -> None:
    """En Windows, ctranslate2 busca cuBLAS/cuDNN en PATH; el wheel de torch con CUDA ya los trae en torch/lib."""
    try:
        import torch
    except ImportError:
        return
    lib = Path(torch.__file__).parent / "lib"
    if (lib / "cublas64_12.dll").exists():
        os.environ["PATH"] = str(lib) + os.pathsep + os.environ.get("PATH", "")
        os.add_dll_directory(str(lib))


def cargar_modelo(nombre: str, dispositivo: str):
    if dispositivo in ("auto", "cuda") and os.name == "nt":
        dlls_cuda_de_torch()
    from faster_whisper import WhisperModel

    if dispositivo in ("auto", "cuda"):
        try:
            return WhisperModel(nombre, device="cuda", compute_type="float16")
        except Exception as e:  # sin cuDNN/cuBLAS, ctranslate2 falla al cargar; se cae a CPU
            if dispositivo == "cuda":
                raise
            print(f"CUDA no disponible para whisper ({e.__class__.__name__}); uso CPU")
    return WhisperModel(nombre, device="cpu", compute_type="int8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("caso")
    p.add_argument("videos", nargs="*")
    p.add_argument("--modelo", default="small")
    p.add_argument("--dispositivo", default="auto", choices=["auto", "cpu", "cuda"])
    a = p.parse_args()

    caso = RAIZ / a.caso
    originales = caso / "originales"
    videos = [originales / v for v in a.videos] or sorted(f for f in originales.iterdir() if f.suffix.lower() in VIDEO)
    pendientes = [v for v in videos if not (caso / "trabajo" / v.stem / "transcripcion.txt").exists()]
    print(f"{len(pendientes)} de {len(videos)} videos sin transcripción")
    if not pendientes:
        return
    modelo = cargar_modelo(a.modelo, a.dispositivo)
    for v in pendientes:
        salida = caso / "trabajo" / v.stem / "transcripcion.txt"
        salida.parent.mkdir(parents=True, exist_ok=True)
        try:
            segs, _ = modelo.transcribe(audio(v), language="es", vad_filter=True)
            lineas = [f"[{int(s.start // 60):02d}:{s.start % 60:04.1f}] {s.text.strip()}" for s in segs]
        except Exception as e:  # un video dañado no detiene el lote
            print(f"[error] {v.name}: {e}")
            continue
        tmp = salida.with_suffix(".tmp")  # se escribe completo o no queda: la siguiente corrida no confunde un archivo a medias con uno terminado
        tmp.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        tmp.replace(salida)
        print(f"[ok] {v.name}: {len(lineas)} segmentos")


if __name__ == "__main__":
    main()
