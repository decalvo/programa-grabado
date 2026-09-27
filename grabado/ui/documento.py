"""El trabajo en curso: foto de origen, recorte y ajustes. Los paneles lo leen y lo modifican."""

from dataclasses import replace
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, Signal

from grabado.proceso import Ajustes, Resultado, cargar_foto, procesar


class Documento(QObject):
    # Se emite cada vez que cambia la foto, la máscara o los ajustes.
    cambiado = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.ruta: Path | None = None
        self.foto: Image.Image | None = None
        # Blanco = sujeto, negro = fondo; None = toda la foto es sujeto.
        self.mascara: Image.Image | None = None
        self.ajustes = Ajustes()

    @property
    def tiene_foto(self) -> bool:
        return self.foto is not None

    def cargar(self, ruta: str | Path) -> None:
        self.ruta = Path(ruta)
        self.foto = cargar_foto(ruta)
        self.mascara = None
        # Los cortes y los ajustes previos dependen de la foto: se vuelve a los automáticos y neutros.
        self.ajustes = replace(self.ajustes, cortes=None, brillo=0, contraste=0, nitidez=0)
        self.cambiado.emit()

    def cambiar_mascara(self, mascara: Image.Image | None) -> None:
        self.mascara = mascara
        self.cambiado.emit()

    def cambiar_ajustes(self, **cambios) -> None:
        nuevos = replace(self.ajustes, **cambios)
        if nuevos != self.ajustes:
            self.ajustes = nuevos
            self.cambiado.emit()

    def procesar(self, ajustes: Ajustes | None = None) -> Resultado:
        if self.foto is None:
            raise RuntimeError("No hay foto cargada")
        return procesar(self.foto, ajustes or self.ajustes, self.mascara)
