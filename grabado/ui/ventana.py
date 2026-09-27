"""Ventana principal: la imagen al centro y los paneles de trabajo a la derecha."""

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from grabado.ui.documento import Documento
from grabado.ui.eliminar_fondo import EliminarFondo
from grabado.ui.panel_exportar import PanelExportar
from grabado.ui.vista import VistaImagen, componer_recorte

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
        self.eliminar_fondo = EliminarFondo(self, self.documento)
        barra.addAction(self.eliminar_fondo.accion)

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

    def _actualizar_vista(self) -> None:
        foto, mascara = self.documento.foto, self.documento.mascara
        self.vista.mostrar(componer_recorte(foto, mascara) if foto is not None and mascara is not None else foto)
