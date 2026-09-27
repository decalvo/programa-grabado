"""De la foto de origen a las capas tramadas, listas para exportar."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from grabado import tonal, tramado
from grabado.tonal import Capa, Cortes

MM_POR_PULGADA = 25.4


@dataclass(frozen=True)
class Ajustes:
    ancho_mm: float = 100.0
    dpi: int = 254
    # None = cortes tonales automáticos.
    cortes: Cortes | None = None
    metodo_tramado: str = tramado.METODO_POR_DEFECTO


@dataclass(frozen=True)
class Resultado:
    gris: np.ndarray
    mascara: np.ndarray | None
    cortes: Cortes
    etiquetas: np.ndarray
    capas: dict[Capa, np.ndarray]
    dpi: int

    @property
    def tamano_mm(self) -> tuple[float, float]:
        alto, ancho = self.gris.shape
        return ancho / self.dpi * MM_POR_PULGADA, alto / self.dpi * MM_POR_PULGADA


def cargar_foto(ruta: str | Path) -> Image.Image:
    """Abre la foto de origen respetando la orientación guardada por la cámara."""
    with Image.open(ruta) as foto:
        return ImageOps.exif_transpose(foto).copy()


def tamano_final_px(tamano_origen: tuple[int, int], ancho_mm: float, dpi: int) -> tuple[int, int]:
    ancho_origen, alto_origen = tamano_origen
    ancho = max(1, round(ancho_mm / MM_POR_PULGADA * dpi))
    alto = max(1, round(ancho * alto_origen / ancho_origen))
    return ancho, alto


def procesar(foto: Image.Image, ajustes: Ajustes, mascara: Image.Image | None = None) -> Resultado:
    """Ajusta la foto al tamaño final, la separa en capas tonales y trama cada capa.

    `mascara` es una imagen del tamaño de la foto: blanco = sujeto, negro = fondo.
    Si no se da y la foto tiene transparencia, se usa su canal alfa.
    """
    if mascara is None and "A" in foto.getbands():
        mascara = foto.getchannel("A")

    tamano = tamano_final_px(foto.size, ajustes.ancho_mm, ajustes.dpi)
    gris = np.asarray(
        foto.convert("RGB").convert("L").resize(tamano, Image.Resampling.LANCZOS), np.float32
    )
    mascara_final = None
    if mascara is not None:
        mascara_final = np.asarray(mascara.convert("L").resize(tamano, Image.Resampling.BILINEAR)) >= 128

    cortes = ajustes.cortes or tonal.cortes_automaticos(gris, mascara_final)
    etiquetas = tonal.separar(gris, cortes, mascara_final)
    densidades = tramado.densidad(gris, cortes, etiquetas)
    capas = tramado.tramar(densidades, etiquetas, ajustes.metodo_tramado)
    return Resultado(gris, mascara_final, cortes, etiquetas, capas, ajustes.dpi)
