"""Configuración compartida. Lee variables de entorno y, si existe, el archivo .env de la raíz.

FARO_CASOS  carpeta de casos (por defecto <raíz>/casos). Conviene que viva fuera del repo.
"""
import os
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parent.parent


def _cargar_env() -> None:
    env = RAIZ_REPO / ".env"
    if not env.exists():
        return
    for linea in env.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_env()


def carpeta_casos() -> Path:
    return Path(os.environ.get("FARO_CASOS") or RAIZ_REPO / "casos").expanduser().resolve()
