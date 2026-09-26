"""Ventana principal: la imagen al centro y los paneles de trabajo a la derecha."""

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from grabado.ui.documento import Documento
from grabado.ui.panel_cortes import PanelCortes
from grabado.ui.panel_exportar import PanelExportar
from grabado.ui.vista import VistaImagen
from grabado.ui.vista_previa import VistaPrevia

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
        self.barra = barra

        self.vista = VistaImagen("Abre una foto para empezar")
        self.vista_previa = VistaPrevia(self.documento)
        self.pestanas = QTabWidget()
        self.pestanas.addTab(self.vista, "Foto")
        self.pestanas.addTab(self.vista_previa, "Vista previa")

        # Cada funcionalidad agrega su panel a esta columna.
        lateral = QWidget()
        self.paneles = QVBoxLayout(lateral)
        self.panel_cortes = PanelCortes(self.documento)
        self.vista_previa.procesado.connect(self.panel_cortes.mostrar_resultado)
        self.paneles.addWidget(self.panel_cortes)
        self.paneles.addWidget(PanelExportar(self.documento))
        self.paneles.addStretch()
        desplazable = QScrollArea()
        desplazable.setWidget(lateral)
        desplazable.setWidgetResizable(True)
        desplazable.setFixedWidth(300)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self.pestanas, stretch=1)
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

    def _actualizar_vista(self) -> None:
        self.vista.mostrar(self.documento.foto)
