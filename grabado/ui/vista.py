"""Widget que muestra una imagen ajustada al espacio disponible, sin deformarla."""

from functools import lru_cache

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy


def a_qimage(imagen: Image.Image) -> QImage:
    if imagen.mode == "RGB":
        # Sin pasar por RGBA: en una foto grande ahorra buena parte del tiempo.
        datos = imagen.tobytes()
        return QImage(datos, imagen.width, imagen.height, imagen.width * 3, QImage.Format.Format_RGB888).copy()
    rgba = imagen.convert("RGBA")
    datos = rgba.tobytes()
    return QImage(datos, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()


GRIS_DAMERO = (205, 205, 205)
BLANCO_DAMERO = (245, 245, 245)


def casilla_damero(tamano: tuple[int, int]) -> int:
    """Lado de cada casilla del damero, en píxeles de la foto."""
    return max(8, min(tamano) // 40)


@lru_cache(maxsize=2)
def _damero(tamano: tuple[int, int]) -> Image.Image:
    ancho, alto = tamano
    casilla = casilla_damero(tamano)
    filas = (np.arange(alto) // casilla)[:, None]
    columnas = (np.arange(ancho) // casilla)[None, :]
    colores = np.array([GRIS_DAMERO, BLANCO_DAMERO], np.uint8)
    return Image.fromarray(colores[(filas + columnas) % 2], "RGB")


def componer_recorte(foto: Image.Image, mascara: Image.Image) -> Image.Image:
    """El recorte sobre un damero gris claro, para que se vea qué parte es fondo."""
    # El damero solo depende del tamaño: se reutiliza entre trazos del retoque.
    resultado = _damero(foto.size).copy()
    sujeto = mascara.convert("L")
    if sujeto.size != foto.size:
        sujeto = sujeto.resize(foto.size)
    sujeto = sujeto.point([0] * 128 + [255] * 128)
    resultado.paste(foto if foto.mode == "RGB" else foto.convert("RGB"), mask=sujeto)
    return resultado


class VistaImagen(QLabel):
    def __init__(self, texto_vacio: str = "") -> None:
        super().__init__(texto_vacio)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._pixmap: QPixmap | None = None
        self._imagen: Image.Image | None = None

    def mostrar(self, imagen: Image.Image | None) -> None:
        # Convertir una foto grande tarda: si es la misma imagen de antes, no se repite.
        if imagen is not None and imagen is self._imagen:
            return
        self._imagen = imagen
        self._pixmap = QPixmap.fromImage(a_qimage(imagen)) if imagen is not None else None
        self._actualizar()

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        self._actualizar()

    def _actualizar(self) -> None:
        if self._pixmap is None:
            self.setPixmap(QPixmap())
            return
        self.setPixmap(
            self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
