"""Registra videos o fotos en un caso: descarga (si es URL) o copia, calcula SHA-256
y guarda la procedencia en casos/<caso>/fuentes.jsonl (cadena de custodia básica).

Uso:
  python scripts/ingerir.py <caso> <url|archivo> [...] [--nota "quién lo envió, cómo"]
  python scripts/ingerir.py <caso> @lista.txt --nota "..."

El original nunca se edita. Si el hash ya está registrado, no se duplica.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))  # con python -I no se agrega solo
from config import carpeta_casos  # noqa: E402

RAIZ = carpeta_casos()


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def ffprobe(ruta: Path) -> dict:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(ruta)],
            capture_output=True, text=True, check=True,
        ).stdout
        return json.loads(out)
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return {}


def descargar(url: str, destino: Path) -> tuple[Path, dict]:
    import yt_dlp

    opciones = {
        "outtmpl": str(destino / "%(extractor_key)s_%(id)s.%(ext)s"),
        "noplaylist": True,
        "writeinfojson": True,
        "quiet": True,
        "noprogress": True,
    }
    if not shutil.which("ffmpeg"):  # sin ffmpeg en el sistema: usa el que trae imageio-ffmpeg
        import imageio_ffmpeg
        opciones["ffmpeg_location"] = imageio_ffmpeg.get_ffmpeg_exe()
    with yt_dlp.YoutubeDL(opciones) as ydl:
        info = ydl.extract_info(url, download=True)
        ruta = Path(info["requested_downloads"][0]["filepath"])
    return ruta, procedencia_de(info, url)


def procedencia_de(info: dict, url: str | None) -> dict:
    publicado = info.get("timestamp")
    return {
        "url": url or info.get("original_url") or info.get("webpage_url"),
        "url_canonica": info.get("webpage_url"),
        "cuenta": info.get("uploader"),
        "cuenta_id": info.get("uploader_id"),
        "titulo": info.get("title"),
        "publicado_utc": datetime.fromtimestamp(publicado, timezone.utc).isoformat() if publicado else None,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                fromfile_prefix_chars="@")  # @lista.txt: una URL o ruta por línea
    p.add_argument("caso")
    p.add_argument("entradas", nargs="+", help="URLs o rutas locales")
    p.add_argument("--nota", default="", help="procedencia: quién lo envió, por qué medio")
    a = p.parse_args()

    caso = RAIZ / a.caso
    originales = caso / "originales"
    originales.mkdir(parents=True, exist_ok=True)
    registro = caso / "fuentes.jsonl"
    vistos = set()
    if registro.exists():
        vistos = {json.loads(l)["sha256"] for l in registro.read_text(encoding="utf-8").splitlines() if l.strip()}

    for entrada in a.entradas:
        procedencia: dict = {"url": None}
        if entrada.startswith(("http://", "https://")):
            try:
                ruta, procedencia = descargar(entrada, originales)
            except Exception as e:  # yt-dlp lanza varios tipos; se reporta y se sigue con el resto
                print(f"[error] {entrada}: {e}")
                continue
        else:
            origen = Path(entrada).resolve()
            if not origen.is_file():
                print(f"[error] no existe: {entrada}")
                continue
            ruta = origen if origen.parent == originales.resolve() else Path(shutil.copy2(origen, originales / origen.name))
            info_json = origen.with_suffix(".info.json")
            if info_json.exists():  # descargado antes con yt-dlp
                procedencia = procedencia_de(json.loads(info_json.read_text(encoding="utf-8")), None)
            procedencia["archivo_recibido"] = origen.name

        h = sha256(ruta)
        if h in vistos:
            print(f"[repetido] {ruta.name} ya estaba registrado")
            continue
        meta = ffprobe(ruta)
        video = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), {})
        fila = {
            "archivo": ruta.name,
            "sha256": h,
            "bytes": ruta.stat().st_size,
            **procedencia,
            "registrado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "duracion_s": float(meta["format"]["duration"]) if meta.get("format", {}).get("duration") else None,
            "resolucion": f"{video.get('width')}x{video.get('height')}" if video else None,
            "creacion_en_archivo": meta.get("format", {}).get("tags", {}).get("creation_time"),
            "nota": a.nota,
        }
        with registro.open("a", encoding="utf-8") as f:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
        vistos.add(h)
        print(f"[ok] {ruta.name}  {h[:16]}…  {fila.get('cuenta') or ''}")


if __name__ == "__main__":
    main()
