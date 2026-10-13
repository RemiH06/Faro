"""Puntaje de atuendo por color: qué fracción del torso y de las piernas de una
persona cae en los rangos HSV de la ficha (atuendo_hsv). No identifica a nadie:
solo prioriza recortes cuya ropa se parece a la descrita.

En ficha.yaml (H 0-179, S y V 0-255, rangos de OpenCV):
  atuendo_hsv:
    torso:   [[40, 60, 50], [85, 255, 255]]     # verde
    piernas: [[95, 40, 40], [125, 200, 220]]    # mezclilla azul
Para colores de piel cercana (beige, caqui), baja la S máxima para no confundirlos con piel.
"""
import cv2
import numpy as np

# Fracciones verticales de la caja de una persona de pie
TORSO = (0.18, 0.50)
PIERNAS = (0.52, 0.90)
PROPORCION_MIN = 1.8  # alto/ancho: por debajo es un acercamiento sin piernas y las zonas no aplican


def fraccion(bgr: np.ndarray, rango) -> float:
    if bgr.size == 0:
        return 0.0
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(rango[0]), np.array(rango[1]))
    return float(mask.mean() / 255)


def puntaje(bgr: np.ndarray, rangos: dict) -> float:
    """Media geométrica de las fracciones por zona; 0 si alguna zona no tiene el color."""
    h, w = bgr.shape[:2]
    if w == 0 or h / w < PROPORCION_MIN:
        return 0.0
    x0, x1 = int(w * 0.15), int(w * 0.85)  # sin bordes, donde suele entrar otra gente
    partes = []
    for zona, (a, b) in (("torso", TORSO), ("piernas", PIERNAS)):
        if zona in rangos:
            partes.append(fraccion(bgr[int(h * a):int(h * b), x0:x1], rangos[zona]))
    return float(np.prod(partes) ** (1 / len(partes))) if partes else 0.0
