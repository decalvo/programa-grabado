"""El trabajo en curso: foto de origen, recorte y ajustes. Los paneles lo leen y lo modifican."""

import io
from dataclasses import replace
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, Signal

from grabado import proyecto
from grabado.proceso import Ajustes, Resultado, cargar_foto, procesar


class Documento(QObject):
    # Se emite cada vez que cambia la foto, la máscara o los ajustes.
    cambiado = Signal()
    # Se emite cuando cambia si hay cambios sin guardar o el archivo del proyecto.
    estado_cambiado = Signal()

    def __init__(self) -> None:
        super().__init__()
        # La foto de origen; al abrir un proyecto, su nombre junto al proyecto (puede no existir):
        # su nombre es la base de lo exportado.
        self.ruta: Path | None = None
        # Bytes del archivo de la foto de origen, para guardarla en el proyecto sin recomprimir.
        self.foto_datos: bytes | None = None
        self.foto: Image.Image | None = None
        # Blanco = sujeto, negro = fondo; None = toda la foto es sujeto.
        self.mascara: Image.Image | None = None
        self.ajustes = Ajustes()
        # Archivo del proyecto, si ya se guardó o se abrió uno.
        self.ruta_proyecto: Path | None = None
        # Hay cambios que no están en el archivo del proyecto.
        self.modificado = False

    @property
    def tiene_foto(self) -> bool:
        return self.foto is not None

    @property
    def nombre(self) -> str | None:
        """Nombre para mostrar: el del proyecto o, si aún no se guardó, el de la foto."""
        if self.ruta_proyecto is not None:
            return self.ruta_proyecto.stem
        return self.ruta.name if self.ruta is not None else None

    def cargar(self, ruta: str | Path) -> None:
        ruta = Path(ruta)
        datos = ruta.read_bytes()
        self.foto = cargar_foto(io.BytesIO(datos))
        self.ruta = ruta
        self.foto_datos = datos
        self.mascara = None
        self.ruta_proyecto = None
        # Los cortes y los ajustes previos dependen de la foto: se vuelve a los automáticos y neutros.
        self.ajustes = replace(self.ajustes, cortes=None, brillo=0, contraste=0, nitidez=0)
        # Recién abierta no hay nada que perder: basta con volver a abrir la foto.
        self._marcar(False)
        self.cambiado.emit()

    def abrir_proyecto(self, ruta: str | Path) -> None:
        """Restaura foto, recorte y ajustes desde el archivo, sin volver a eliminar el fondo."""
        ruta = Path(ruta)
        abierto = proyecto.abrir(ruta)
        foto = abierto.cargar_foto()
        self.ruta = ruta.parent / abierto.nombre_foto
        self.foto_datos = abierto.foto_datos
        self.foto = foto
        self.mascara = abierto.mascara
        self.ajustes = abierto.ajustes
        self.ruta_proyecto = ruta
        self._marcar(False)
        self.cambiado.emit()

    def guardar_proyecto(self, ruta: str | Path | None = None) -> None:
        """Guarda en `ruta` o, si no se da, en el archivo del proyecto ya abierto o guardado."""
        if self.foto_datos is None or self.ruta is None:
            raise RuntimeError("No hay foto cargada")
        ruta = Path(ruta) if ruta is not None else self.ruta_proyecto
        if ruta is None:
            raise RuntimeError("Falta el archivo del proyecto")
        proyecto.guardar(ruta, proyecto.Proyecto(self.ruta.name, self.foto_datos, self.mascara, self.ajustes))
        self.ruta_proyecto = ruta
        self._marcar(False)

    def cambiar_mascara(self, mascara: Image.Image | None) -> None:
        self.mascara = mascara
        self._marcar(True)
        self.cambiado.emit()

    def cambiar_ajustes(self, **cambios) -> None:
        nuevos = replace(self.ajustes, **cambios)
        if nuevos != self.ajustes:
            self.ajustes = nuevos
            self._marcar(True)
            self.cambiado.emit()

    def procesar(self, ajustes: Ajustes | None = None) -> Resultado:
        if self.foto is None:
            raise RuntimeError("No hay foto cargada")
        return procesar(self.foto, ajustes or self.ajustes, self.mascara)

    def _marcar(self, modificado: bool) -> None:
        # Sin foto no hay trabajo que guardar (p. ej. al cambiar el DPI para la plantilla de calibración).
        self.modificado = modificado and self.tiene_foto
        self.estado_cambiado.emit()
