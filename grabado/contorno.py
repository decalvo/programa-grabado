"""Contorno: la línea que se graba siguiendo el borde del sujeto, como un trazo dibujado.

La línea va por dentro del sujeto, pegada al borde del recorte: nada se graba fuera de él,
así el grabado mide lo mismo con o sin contorno y la línea no se sale del lienzo. A cambio,
el contorno tapa una franja del sujeto del ancho de la línea.

Solo se traza donde el sujeto toca el fondo. Donde el sujeto llega al borde del lienzo
(por ejemplo, un retrato cortado a la altura del pecho) no se traza nada: la foto simplemente termina ahí.
"""

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

MM_POR_PULGADA = 25.4

GROSOR_POR_DEFECTO_MM = 1.0

# Suavizado del borde, en proporción al grosor de la línea: quita los dientes del recorte
# y los pelitos sueltos más finos que la línea, que harían un trazo tembloroso.
SUAVIZADO_POR_GROSOR = 0.5


def grosor_px(grosor_mm: float, dpi: int) -> int:
    """Grosor de la línea en píxeles a la resolución dada; al menos 1 píxel."""
    return max(1, round(grosor_mm / MM_POR_PULGADA * dpi))


def suavizar(mascara: np.ndarray, radio: float) -> np.ndarray:
    """Redondea el borde de la máscara (True = sujeto) difuminándola y volviendo a umbralizar."""
    if radio <= 0:
        return mascara.copy()
    imagen = Image.fromarray(np.where(mascara, 255, 0).astype(np.uint8), "L")
    return np.asarray(imagen.filter(ImageFilter.GaussianBlur(radio))) >= 128


def calcular(mascara: np.ndarray, grosor: int) -> tuple[np.ndarray, np.ndarray]:
    """Contorno de una máscara (True = sujeto) como una franja de `grosor` píxeles por dentro del borde.

    Devuelve `(linea, interior)`: `linea` es True donde se graba el contorno e `interior` donde
    quedan las capas tonales, dentro de la línea. Fuera de los dos no se graba nada, ni siquiera
    los pelitos sueltos del recorte que el suavizado deja fuera de la línea.
    """
    suave = suavizar(mascara, grosor * SUAVIZADO_POR_GROSOR)
    if suave.all() or not suave.any():
        return np.zeros_like(suave), suave
    # Distancia de cada píxel del sujeto al píxel de fondo más cercano (1 = pegado al fondo).
    # El exterior del lienzo no cuenta como fondo, así que ahí no hay línea.
    distancia = ndimage.distance_transform_edt(suave)
    linea = suave & (distancia <= grosor)
    return linea, suave & ~linea
