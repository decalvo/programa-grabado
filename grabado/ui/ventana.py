"""Ventana principal: la imagen al centro y los paneles de trabajo a la derecha."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from grabado import calibracion
from grabado.ui.documento import Documento
from grabado.ui.panel_exportar import PanelExportar
from grabado.ui.vista import VistaImagen

FILTRO_FOTOS = "Fotos (*.jpg *.jpeg *.png *.bmp *.webp)"


class Ventana(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Programa grabado")
        self.resize(1200, 800)
        self.documento = Documento()

        barra = self.addToolBar("Principal")
        barra.setMovable(False)
        abrir = QAction("Abrir foto…", self)
        abrir.setShortcut(QKeySequence.StandardKey.Open)
        abrir.triggered.connect(self._abrir)
        barra.addAction(abrir)
        calibrar = QAction("Plantilla de calibración…", self)
        calibrar.triggered.connect(self._exportar_calibracion)
        barra.addAction(calibrar)
        self.barra = barra

        self.vista = VistaImagen("Abre una foto para empezar")

        # Cada funcionalidad agrega su panel a esta columna.
        lateral = QWidget()
        self.paneles = QVBoxLayout(lateral)
        self.paneles.addWidget(PanelExportar(self.documento))
        self.paneles.addStretch()
        desplazable = QScrollArea()
        desplazable.setWidget(lateral)
        desplazable.setWidgetResizable(True)
        desplazable.setFixedWidth(300)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self.vista, stretch=1)
        layout.addWidget(desplazable)
        self.setCentralWidget(central)

        self.documento.cambiado.connect(self._actualizar_vista)

    def _abrir(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir foto", "", FILTRO_FOTOS)
        if not ruta:
            return
        try:
            self.documento.cargar(ruta)
        except OSError as error:
            QMessageBox.warning(self, "No se pudo abrir la foto", str(error))
            return
        self.setWindowTitle(f"Programa grabado - {self.documento.ruta.name}")

    def _exportar_calibracion(self) -> None:
        ajustes = self.documento.ajustes
        inicio = str(self.documento.ruta.parent) if self.documento.ruta else ""
        carpeta = QFileDialog.getExistingDirectory(self, "Carpeta para la plantilla de calibración", inicio)
        if not carpeta:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            plantilla = calibracion.crear(ajustes.dpi, ajustes.metodo_tramado)
            archivos = calibracion.exportar(plantilla, carpeta)
        except OSError as error:
            QMessageBox.warning(self, "No se pudo exportar la plantilla", str(error))
            return
        finally:
            QApplication.restoreOverrideCursor()
        ancho_mm, alto_mm = plantilla.tamano_mm
        QMessageBox.information(
            self,
            "Plantilla de calibración lista",
            f"Lienzo de {ancho_mm:.1f} × {alto_mm:.1f} mm a {ajustes.dpi} DPI.\n"
            "Archivos creados:\n" + "\n".join(a.name for a in archivos),
        )

    def _actualizar_vista(self) -> None:
        self.vista.mostrar(self.documento.foto)
