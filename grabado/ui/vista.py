"""Widget que muestra una imagen ajustada al espacio disponible, sin deformarla."""

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy


def a_qimage(imagen: Image.Image) -> QImage:
    rgba = imagen.convert("RGBA")
    datos = rgba.tobytes()
    return QImage(datos, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()


class VistaImagen(QLabel):
    def __init__(self, texto_vacio: str = "") -> None:
        super().__init__(texto_vacio)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._pixmap: QPixmap | None = None

    def mostrar(self, imagen: Image.Image | None) -> None:
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
