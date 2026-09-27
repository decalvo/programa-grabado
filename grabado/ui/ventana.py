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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from grabado import calibracion
from grabado.ui.documento import Documento
from grabado.ui.eliminar_fondo import EliminarFondo
from grabado.ui.panel_cortes import PanelCortes
from grabado.ui.panel_exportar import PanelExportar
from grabado.ui.panel_tramado import PanelTramado
from grabado.ui.retoque import PanelRetoque
from grabado.ui.vista import VistaImagen, componer_recorte
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
        calibrar = QAction("Plantilla de calibración…", self)
        calibrar.triggered.connect(self._exportar_calibracion)
        barra.addAction(calibrar)
        self.barra = barra
        self.eliminar_fondo = EliminarFondo(self, self.documento)
        barra.addAction(self.eliminar_fondo.accion)

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
        self.panel_retoque = PanelRetoque(self.documento, self.vista)
        self.panel_retoque.activado.connect(lambda: self.pestanas.setCurrentWidget(self.vista))
        self.paneles.addWidget(self.panel_retoque)
        self.paneles.addWidget(self.panel_cortes)
        self.paneles.addWidget(PanelTramado(self.documento))
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

        # Recorte ya compuesto, para no rehacerlo cuando solo cambian los ajustes.
        self._recorte = (None, None, None)
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
        foto, mascara = self.documento.foto, self.documento.mascara
        if foto is None or mascara is None:
            self.vista.mostrar(foto)
            return
        foto_previa, mascara_previa, recorte = self._recorte
        if foto is not foto_previa or mascara is not mascara_previa:
            recorte = componer_recorte(foto, mascara)
            self._recorte = (foto, mascara, recorte)
        self.vista.mostrar(recorte)
