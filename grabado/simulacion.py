"""Vista previa del grabado: simula cómo queda el tramado de cada capa tonal sobre la madera."""

import numpy as np
from PIL import Image

from grabado.proceso import Resultado, tamano_final_px
from grabado.tonal import CAPAS_GRABADAS, FONDO, Capa

Color = tuple[int, int, int]

# Tono de café que deja cada capa grabada. Son valores de referencia: más adelante
# pueden reemplazarse por los que mida la plantilla de calibración.
PALETA: dict[Capa, Color] = {
    Capa.NEGRO: (58, 34, 20),
    Capa.OSCURO: (108, 68, 38),
    Capa.MEDIO: (160, 114, 72),
}

# Claro y los huecos del tramado no se graban: quedan como madera natural.
MADERA: Color = (226, 192, 146)

# Fuera del sujeto. Se muestra en gris para distinguirlo de la madera del sujeto.
COLOR_FONDO: Color = (190, 190, 190)


def dpi_para_caja(
    tamano_origen: tuple[int, int], ancho_mm: float, dpi: int, caja: tuple[int, int]
) -> int:
    """DPI con el que el grabado cabe en `caja` (ancho, alto en px), sin pasar del DPI de exportación.

    La vista previa se calcula a este DPI para ir rápido: el tramado queda a la escala de la pantalla.
    """
    ancho_px, alto_px = tamano_final_px(tamano_origen, ancho_mm, dpi)
    escala = min(caja[0] / ancho_px, caja[1] / alto_px, 1.0)
    return max(1, int(dpi * escala))


def simular(
    resultado: Resultado,
    paleta: dict[Capa, Color] = PALETA,
    madera: Color = MADERA,
    fondo: Color = COLOR_FONDO,
) -> Image.Image:
    """Imagen RGB del tamaño del resultado con cada punto grabado en el café de su capa."""
    alto, ancho = resultado.etiquetas.shape
    pixeles = np.empty((alto, ancho, 3), np.uint8)
    pixeles[:] = madera
    pixeles[resultado.etiquetas == FONDO] = fondo
    for capa in CAPAS_GRABADAS:
        pixeles[resultado.capas[capa]] = paleta[capa]
    return Image.fromarray(pixeles, "RGB")
