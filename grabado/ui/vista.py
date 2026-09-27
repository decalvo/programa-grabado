"""Widget que muestra una imagen ajustada al espacio disponible, sin deformarla."""

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy


def a_qimage(imagen: Image.Image) -> QImage:
    rgba = imagen.convert("RGBA")
    datos = rgba.tobytes()
    return QImage(datos, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()


GRIS_DAMERO = (205, 205, 205)
BLANCO_DAMERO = (245, 245, 245)


def componer_recorte(foto: Image.Image, mascara: Image.Image) -> Image.Image:
    """El recorte sobre un damero gris claro, para que se vea qué parte es fondo."""
    ancho, alto = foto.size
    casilla = max(8, min(ancho, alto) // 40)
    filas = (np.arange(alto) // casilla)[:, None]
    columnas = (np.arange(ancho) // casilla)[None, :]
    damero = np.where(((filas + columnas) % 2 == 0)[..., None], GRIS_DAMERO, BLANCO_DAMERO).astype(np.uint8)
    resultado = Image.fromarray(damero, "RGB")
    sujeto = mascara.convert("L").resize(foto.size).point(lambda v: 255 if v >= 128 else 0)
    resultado.paste(foto.convert("RGB"), mask=sujeto)
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
