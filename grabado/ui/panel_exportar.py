"""Panel de tamaño final y exportación de las capas a BMP."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from grabado.exportar import exportar
from grabado.proceso import MM_POR_PULGADA, tamano_final_px
from grabado.ui.documento import Documento


class PanelExportar(QGroupBox):
    def __init__(self, documento: Documento) -> None:
        super().__init__("Exportar")
        self.documento = documento

        self.ancho = QDoubleSpinBox()
        self.ancho.setRange(10, 1000)
        self.ancho.setDecimals(1)
        self.ancho.setSuffix(" mm")
        self.ancho.setValue(documento.ajustes.ancho_mm)
        self.ancho.valueChanged.connect(lambda v: documento.cambiar_ajustes(ancho_mm=v))

        self.dpi = QSpinBox()
        self.dpi.setRange(50, 1200)
        self.dpi.setSuffix(" DPI")
        self.dpi.setValue(documento.ajustes.dpi)
        self.dpi.valueChanged.connect(lambda v: documento.cambiar_ajustes(dpi=v))

        self.info = QLabel()
        self.info.setWordWrap(True)

        self.boton = QPushButton("Exportar capas…")
        self.boton.clicked.connect(self._exportar)

        formulario = QFormLayout()
        formulario.addRow("Ancho final", self.ancho)
        formulario.addRow("Resolución", self.dpi)

        layout = QVBoxLayout(self)
        layout.addLayout(formulario)
        layout.addWidget(self.info)
        layout.addWidget(self.boton)

        documento.cambiado.connect(self._actualizar)
        self._actualizar()

    def _actualizar(self) -> None:
        doc = self.documento
        self.boton.setEnabled(doc.tiene_foto)
        if not doc.tiene_foto:
            self.info.setText("Abre una foto para empezar.")
            return
        ancho_px, alto_px = tamano_final_px(doc.foto.size, doc.ajustes.ancho_mm, doc.ajustes.dpi)
        alto_mm = alto_px / doc.ajustes.dpi * MM_POR_PULGADA
        intervalo = MM_POR_PULGADA / doc.ajustes.dpi
        self.info.setText(
            f"Alto: {alto_mm:.1f} mm\n{ancho_px} × {alto_px} px\nIntervalo: {intervalo:.3f} mm"
        )

    def _exportar(self) -> None:
        doc = self.documento
        carpeta = QFileDialog.getExistingDirectory(self, "Carpeta de exportación", str(doc.ruta.parent))
        if not carpeta:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            archivos = exportar(doc.procesar(), carpeta, doc.ruta.stem)
        finally:
            QApplication.restoreOverrideCursor()
        QMessageBox.information(
            self,
            "Exportación lista",
            "Archivos creados:\n" + "\n".join(a.name for a in archivos),
        )
