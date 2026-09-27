"""Ventana principal: la imagen al centro y los paneles de trabajo a la derecha."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
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

from grabado import calibracion, proyecto
from grabado.ui.documento import Documento
from grabado.ui.eliminar_fondo import EliminarFondo
from grabado.ui.panel_ajustes_previos import PanelAjustesPrevios
from grabado.ui.panel_contorno import PanelContorno
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
        self.resize(1200, 800)
        self.documento = Documento()

        abrir = QAction("Abrir foto…", self)
        abrir.setShortcut(QKeySequence.StandardKey.Open)
        abrir.triggered.connect(self._abrir)
        self.accion_abrir_proyecto = QAction("Abrir proyecto…", self)
        self.accion_abrir_proyecto.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.accion_abrir_proyecto.triggered.connect(self._abrir_proyecto)
        self.accion_guardar = QAction("Guardar proyecto", self)
        self.accion_guardar.setShortcut(QKeySequence.StandardKey.Save)
        self.accion_guardar.setToolTip("Guarda la foto, el recorte y todos los ajustes para seguir más tarde (Ctrl+S)")
        self.accion_guardar.triggered.connect(self.guardar)
        self.accion_guardar_como = QAction("Guardar proyecto como…", self)
        self.accion_guardar_como.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.accion_guardar_como.triggered.connect(self.guardar_como)
        calibrar = QAction("Plantilla de calibración…", self)
        calibrar.triggered.connect(self._exportar_calibracion)
        self.eliminar_fondo = EliminarFondo(self, self.documento)

        archivo = self.menuBar().addMenu("&Archivo")
        for accion in (abrir, self.accion_abrir_proyecto, None, self.accion_guardar, self.accion_guardar_como,
                       None, calibrar):
            if accion is None:
                archivo.addSeparator()
            else:
                archivo.addAction(accion)

        barra = self.addToolBar("Principal")
        barra.setMovable(False)
        barra.addAction(abrir)
        barra.addAction(self.accion_abrir_proyecto)
        barra.addAction(self.accion_guardar)
        barra.addSeparator()
        barra.addAction(calibrar)
        self.barra = barra
        barra.addAction(self.eliminar_fondo.accion)

        self.vista = VistaImagen("Abre una foto para empezar")
        self.vista_previa = VistaPrevia(self.documento)
        self.pestanas = QTabWidget()
        self.pestanas.addTab(self.vista, "Foto")
        self.pestanas.addTab(self.vista_previa, "Vista previa")

        # Cada funcionalidad agrega su panel a esta columna.
        lateral = QWidget()
        self.paneles = QVBoxLayout(lateral)
        self.panel_ajustes_previos = PanelAjustesPrevios(self.documento)
        self.panel_cortes = PanelCortes(self.documento)
        self.vista_previa.procesado.connect(self.panel_cortes.mostrar_resultado)
        self.panel_retoque = PanelRetoque(self.documento, self.vista)
        self.panel_retoque.activado.connect(lambda: self.pestanas.setCurrentWidget(self.vista))
        self.paneles.addWidget(self.panel_retoque)
        self.paneles.addWidget(self.panel_ajustes_previos)
        self.paneles.addWidget(self.panel_cortes)
        self.panel_tramado = PanelTramado(self.documento)
        self.paneles.addWidget(self.panel_tramado)
        self.panel_contorno = PanelContorno(self.documento)
        self.paneles.addWidget(self.panel_contorno)
        self.panel_exportar = PanelExportar(self.documento)
        self.paneles.addWidget(self.panel_exportar)
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
        self.documento.estado_cambiado.connect(self._actualizar_titulo)
        self._actualizar_titulo()

    # --- Foto y proyecto -----------------------------------------------------------------

    def _carpeta_inicial(self) -> str:
        doc = self.documento
        ruta = doc.ruta_proyecto or doc.ruta
        return str(ruta.parent) if ruta is not None else ""

    def _abrir(self) -> None:
        if not self.confirmar_descartar():
            return
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir foto", self._carpeta_inicial(), FILTRO_FOTOS)
        if not ruta:
            return
        try:
            self.documento.cargar(ruta)
        except OSError as error:
            QMessageBox.warning(self, "No se pudo abrir la foto", str(error))

    def _abrir_proyecto(self) -> None:
        if not self.confirmar_descartar():
            return
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", self._carpeta_inicial(), proyecto.FILTRO)
        if not ruta:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.documento.abrir_proyecto(ruta)
        except (OSError, proyecto.ProyectoInvalido) as error:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "No se pudo abrir el proyecto", str(error))
            return
        QApplication.restoreOverrideCursor()

    def guardar(self) -> bool:
        """Guarda en el archivo del proyecto; la primera vez pregunta dónde. Devuelve si se guardó."""
        if self.documento.ruta_proyecto is None:
            return self.guardar_como()
        return self._guardar_en(self.documento.ruta_proyecto)

    def guardar_como(self) -> bool:
        doc = self.documento
        if not doc.tiene_foto:
            return False
        sugerida = doc.ruta_proyecto or doc.ruta.with_suffix(proyecto.EXTENSION)
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar proyecto", str(sugerida), proyecto.FILTRO)
        if not ruta:
            return False
        ruta = Path(ruta)
        if ruta.suffix.lower() != proyecto.EXTENSION:
            ruta = ruta.with_name(ruta.name + proyecto.EXTENSION)
        return self._guardar_en(ruta)

    def _guardar_en(self, ruta: Path) -> bool:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.documento.guardar_proyecto(ruta)
        except OSError as error:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "No se pudo guardar el proyecto", str(error))
            return False
        QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"Proyecto guardado en {ruta}", 5000)
        return True

    def confirmar_descartar(self) -> bool:
        """Si hay cambios sin guardar, pregunta qué hacer. Devuelve si se puede seguir."""
        if not self.documento.modificado:
            return True
        respuesta = QMessageBox.question(
            self,
            "Cambios sin guardar",
            f"¿Guardar los cambios de «{self.documento.nombre}» en el proyecto?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if respuesta == QMessageBox.StandardButton.Save:
            return self.guardar()
        return respuesta == QMessageBox.StandardButton.Discard

    def closeEvent(self, evento: QCloseEvent) -> None:
        if self.confirmar_descartar():
            evento.accept()
        else:
            evento.ignore()

    def _actualizar_titulo(self) -> None:
        doc = self.documento
        # "[*]" muestra el asterisco de cambios sin guardar cuando la ventana está modificada.
        self.setWindowTitle(f"{doc.nombre}[*] - Programa grabado" if doc.nombre else "Programa grabado")
        self.setWindowModified(doc.modificado)
        self.accion_guardar.setEnabled(doc.tiene_foto)
        self.accion_guardar_como.setEnabled(doc.tiene_foto)

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
