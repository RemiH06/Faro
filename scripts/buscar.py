"""Busca candidatos a la persona de la ficha en los videos de un caso.

1. YOLO detecta y sigue personas (ByteTrack): cada persona queda como un "track".
2. Cada recorte se puntúa por el color de su ropa contra atuendo_hsv de la ficha
   (ver atuendo.py). Con --clip, o si la ficha no trae colores, se usa CLIP contra
   referencias/ y descripcion_clip.
3. Por video deja en trabajo/<video>/: candidatos.csv, un recorte y un fotograma
   con recuadro por track, y hoja.jpg con los mejores para revisión humana.

No hay reconocimiento facial: solo color de ropa y, opcionalmente, apariencia
general con CLIP. El puntaje ordena candidatos; no identifica a nadie.

Uso:
  python scripts/buscar.py <caso> [video ...] [--fps 3] [--top 20] [--yolo yolo11s.pt]
"""
import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np
import open_clip
import torch
import yaml
from PIL import Image, ImageDraw
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent))  # con python -I no se agrega solo
import atuendo  # noqa: E402
from config import carpeta_casos  # noqa: E402

RAIZ = carpeta_casos()
VIDEO = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
IMAGEN = {".jpg", ".jpeg", ".png", ".webp"}
ALTO_MIN = 60  # px; recortes más chicos no dicen nada útil


def mmss(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


class Clip:
    def __init__(self, modelo="ViT-B-32", pesos="laion2b_s34b_b79k"):
        self.model, _, self.prep = open_clip.create_model_and_transforms(modelo, pretrained=pesos)
        self.tok = open_clip.get_tokenizer(modelo)
        self.model.eval()

    @torch.no_grad()
    def imagenes(self, imgs: list[Image.Image]) -> np.ndarray:
        x = torch.stack([self.prep(i) for i in imgs])
        e = self.model.encode_image(x)
        return (e / e.norm(dim=-1, keepdim=True)).numpy()

    @torch.no_grad()
    def textos(self, frases: list[str]) -> np.ndarray:
        e = self.model.encode_text(self.tok(frases))
        return (e / e.norm(dim=-1, keepdim=True)).numpy()


def procesar(video: Path, salida: Path, yolo: YOLO, clip, refs, textos, rangos, fps_obj: float, top: int):
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    paso = max(1, round(fps / fps_obj))
    tracks: dict[int, dict] = {}
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if n % paso:
            n += 1
            continue
        t = n / fps
        n += 1
        r = yolo.track(frame, persist=True, classes=[0], tracker="bytetrack.yaml", verbose=False)[0]
        if r.boxes.id is None:
            continue
        cajas, ids = [], []
        for (x1, y1, x2, y2), tid in zip(r.boxes.xyxy.tolist(), r.boxes.id.int().tolist()):
            if y2 - y1 >= ALTO_MIN:
                cajas.append((int(x1), int(y1), int(x2), int(y2)))
                ids.append(tid)
        if not cajas:
            continue
        bgr = [frame[y1:y2, x1:x2] for x1, y1, x2, y2 in cajas]
        s_atu = [atuendo.puntaje(b, rangos) for b in bgr] if rangos else [0.0] * len(bgr)
        s_img = s_txt = np.zeros(len(bgr))
        if clip:
            emb = clip.imagenes([Image.fromarray(cv2.cvtColor(b, cv2.COLOR_BGR2RGB)) for b in bgr])
            if refs is not None:
                s_img = (emb @ refs.T).max(axis=1)
            if textos is not None:
                s_txt = (emb @ textos.T).max(axis=1)
        for i, tid in enumerate(ids):
            tr = tracks.setdefault(tid, {"ini": t, "fin": t, "mejor": -1.0, "atu": [], "img": [], "txt": []})
            tr["fin"] = t
            tr["atu"].append(s_atu[i])
            tr["img"].append(float(s_img[i]))
            tr["txt"].append(float(s_txt[i]))
            puntaje = s_atu[i] if rangos else float(s_img[i]) + float(s_txt[i])
            if puntaje > tr["mejor"]:
                tr.update(mejor=puntaje, t=t, caja=cajas[i], recorte=Image.fromarray(cv2.cvtColor(bgr[i], cv2.COLOR_BGR2RGB)))

    if not tracks:
        cap.release()
        print(f"  sin personas detectadas en {video.name}")
        return
    (salida / "recortes").mkdir(parents=True, exist_ok=True)
    (salida / "contexto").mkdir(exist_ok=True)
    orden = sorted(tracks.items(), key=lambda kv: kv[1]["mejor"], reverse=True)
    with (salida / "candidatos.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rango", "track", "puntaje", "atuendo_max", "sim_ref_max", "sim_texto_max", "t_mejor", "t_ini", "t_fin", "recorte"])
        for rango, (tid, tr) in enumerate(orden, 1):
            nombre = f"{rango:03d}_track{tid}_{mmss(tr['t']).replace(':', 'm')}s.jpg"
            if rango <= top:
                tr["recorte"].save(salida / "recortes" / nombre, quality=92)
                cap.set(cv2.CAP_PROP_POS_MSEC, tr["t"] * 1000)  # el fotograma completo se relee solo para los mejores
                ok, frame = cap.read()
                if ok:
                    ctx = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    ImageDraw.Draw(ctx).rectangle(tr["caja"], outline=(0, 255, 0), width=3)
                    ctx.save(salida / "contexto" / nombre, quality=88)
            w.writerow([rango, tid, f"{tr['mejor']:.3f}", f"{max(tr['atu']):.3f}", f"{max(tr['img']):.3f}",
                        f"{max(tr['txt']):.3f}", mmss(tr["t"]), mmss(tr["ini"]), mmss(tr["fin"]), nombre if rango <= top else ""])
    cap.release()
    hoja(orden[:top], salida / "hoja.jpg")
    print(f"  {len(tracks)} personas seguidas; hoja con {min(top, len(orden))} candidatos en {salida}")


def hoja(items, destino: Path, ancho=150, alto=230, cols=5):
    filas = (len(items) + cols - 1) // cols
    lienzo = Image.new("RGB", (cols * ancho, filas * (alto + 18)), "white")
    d = ImageDraw.Draw(lienzo)
    for i, (tid, tr) in enumerate(items):
        im = tr["recorte"].copy()
        im.thumbnail((ancho, alto))
        x, y = (i % cols) * ancho, (i // cols) * (alto + 18)
        lienzo.paste(im, (x + (ancho - im.width) // 2, y))
        d.text((x + 3, y + alto + 2), f"#{i + 1} {mmss(tr['t'])} id{tid}", fill="black")
    lienzo.save(destino, quality=90)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("caso")
    p.add_argument("videos", nargs="*", help="nombres dentro de originales/ (por defecto, todos)")
    p.add_argument("--fps", type=float, default=3, help="fotogramas analizados por segundo")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--yolo", default="yolo11s.pt", help="yolo11n.pt es más rápido en CPU; yolo11m.pt en GPU")
    p.add_argument("--solo-nuevos", action="store_true", help="salta videos que ya tienen trabajo/<video>/candidatos.csv")
    p.add_argument("--clip", action="store_true", help="agrega similitud CLIP (lento en CPU; poco útil en multitudes)")
    a = p.parse_args()

    caso = RAIZ / a.caso
    ficha = yaml.safe_load((caso / "ficha.yaml").read_text(encoding="utf-8"))
    rangos = ficha.get("atuendo_hsv") or {}
    clip = Clip() if a.clip or not rangos else None
    archivos_ref = sorted(f for f in (caso / "referencias").glob("*") if f.suffix.lower() in IMAGEN)
    frases = ficha.get("descripcion_clip") or []
    refs = clip.imagenes([Image.open(f).convert("RGB") for f in archivos_ref]) if clip and archivos_ref else None
    textos = clip.textos(frases) if clip and frases else None
    print(f"atuendo: {list(rangos) or 'no'}; CLIP: {'sí' if clip else 'no'}")

    originales = caso / "originales"
    videos = [originales / v for v in a.videos] or sorted(f for f in originales.iterdir() if f.suffix.lower() in VIDEO)
    if a.solo_nuevos:
        videos = [v for v in videos if not (caso / "trabajo" / v.stem / "candidatos.csv").exists()]
    for v in videos:
        print(f"→ {v.name}")
        yolo = YOLO(a.yolo)  # nuevo por video para que el tracker no arrastre ids
        procesar(v, caso / "trabajo" / v.stem, yolo, clip, refs, textos, rangos, a.fps, a.top)


if __name__ == "__main__":
    main()
