"""Botón "Eliminar fondo": corre la IA en otro hilo y guarda la máscara del sujeto en el documento."""

import time
from collections.abc import Callable

from PIL import Image
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QProgressBar

from grabado import fondo
from grabado.ui.documento import Documento


class _Hilo(QThread):
    terminado = Signal(object, float)  # máscara, segundos
    fallo = Signal(str)

    def __init__(self, recortador: Callable[[Image.Image], Image.Image], foto: Image.Image) -> None:
        super().__init__()
        self._recortador = recortador
        self._foto = foto

    def run(self) -> None:
        inicio = time.perf_counter()
        try:
            mascara = self._recortador(self._foto)
        except Exception as error:  # noqa: BLE001 - cualquier fallo se muestra al usuario
            self.fallo.emit(str(error) or type(error).__name__)
            return
        self.terminado.emit(mascara, time.perf_counter() - inicio)


class EliminarFondo(QObject):
    """Acción de la barra que genera el recorte sin congelar la ventana."""

    # Se emite al terminar (bien o mal); útil para pruebas.
    listo = Signal()

    def __init__(
        self,
        ventana: QMainWindow,
        documento: Documento,
        recortador: Callable[[Image.Image], Image.Image] | None = None,
    ) -> None:
        super().__init__(ventana)
        self._ventana = ventana
        self._documento = documento
        self._recortador = recortador or fondo.Recortador()
        self._hilo: _Hilo | None = None
        self._foto_en_curso: Image.Image | None = None
        self._descargando = False
        self._error: str | None = None

        self.accion = QAction("Eliminar fondo", ventana)
        self.accion.setToolTip("Recorta al sujeto con IA local; el fondo no se graba")
        self.accion.triggered.connect(self.ejecutar)

        self._ocupado = QProgressBar()
        self._ocupado.setRange(0, 0)  # Indeterminada.
        self._ocupado.setMaximumWidth(150)
        self._ocupado.hide()
        ventana.statusBar().addPermanentWidget(self._ocupado)

        documento.cambiado.connect(self._actualizar_estado)
        self._actualizar_estado()

    @property
    def ocupado(self) -> bool:
        return self._hilo is not None

    def ejecutar(self) -> None:
        foto = self._documento.foto
        if foto is None or self.ocupado:
            return
        mensaje = "Eliminando fondo…"
        self._descargando = isinstance(self._recortador, fondo.Recortador) and not fondo.modelo_descargado(
            self._recortador.modelo
        )
        if self._descargando:
            mensaje = f"Descargando el modelo de IA (solo la primera vez, {fondo.TAMANO_MODELO_MB} MB)…"
        self._ventana.statusBar().showMessage(mensaje)
        self._ocupado.show()
        QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)

        self._foto_en_curso = foto
        self._hilo = _Hilo(self._recortador, foto)
        self._hilo.terminado.connect(self._terminar)
        self._hilo.fallo.connect(self._fallar)
        self._hilo.finished.connect(self._limpiar)
        self._actualizar_estado()
        self._hilo.start()

    def _terminar(self, mascara: Image.Image, segundos: float) -> None:
        if self._documento.foto is not self._foto_en_curso:
            self._ventana.statusBar().clearMessage()
            return  # Se abrió otra foto mientras tanto.
        self._documento.cambiar_mascara(mascara)
        dispositivo = getattr(self._recortador, "dispositivo", None)
        donde = f" en {dispositivo}" if dispositivo else ""
        self._ventana.statusBar().showMessage(f"Fondo eliminado{donde} ({segundos:.1f} s)", 8000)

    def _fallar(self, error: str) -> None:
        self._error = error

    def _limpiar(self) -> None:
        if self._hilo is not None:
            self._hilo.deleteLater()
        self._hilo = None
        self._foto_en_curso = None
        self._ocupado.hide()
        QApplication.restoreOverrideCursor()
        self._actualizar_estado()
        error, self._error = self._error, None
        if error is not None:
            self._ventana.statusBar().clearMessage()
            if self._descargando:
                error = "La primera vez se necesita internet para descargar el modelo de IA.\n\n" + error
            QMessageBox.warning(self._ventana, "No se pudo eliminar el fondo", error)
        self.listo.emit()

    def _actualizar_estado(self) -> None:
        self.accion.setEnabled(self._documento.tiene_foto and not self.ocupado)
