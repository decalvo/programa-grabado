"""Panel para agregar el contorno: una línea grabada por dentro del borde del sujeto."""

from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QVBoxLayout

from grabado.ui.documento import Documento

# Sin recorte no hay borde del sujeto que seguir: solo estaría el rectángulo de la foto.
AVISO_SIN_RECORTE = "Elimina el fondo para poder agregar el contorno."


class PanelContorno(QGroupBox):
    def __init__(self, documento: Documento) -> None:
        super().__init__("Contorno")
        self.documento = documento

        self.activar = QCheckBox("Agregar contorno")
        self.activar.toggled.connect(lambda v: documento.cambiar_ajustes(contorno=v))

        self.grosor = QDoubleSpinBox()
        self.grosor.setRange(0.1, 10.0)
        self.grosor.setDecimals(1)
        self.grosor.setSingleStep(0.1)
        self.grosor.setSuffix(" mm")
        self.grosor.valueChanged.connect(lambda v: documento.cambiar_ajustes(grosor_contorno_mm=v))

        self.aviso = QLabel(AVISO_SIN_RECORTE)
        self.aviso.setWordWrap(True)

        formulario = QFormLayout()
        formulario.addRow("Grosor", self.grosor)
        layout = QVBoxLayout(self)
        layout.addWidget(self.activar)
        layout.addLayout(formulario)
        layout.addWidget(self.aviso)

        documento.cambiado.connect(self._actualizar)
        self._actualizar()

    def _actualizar(self) -> None:
        ajustes = self.documento.ajustes
        hay_recorte = self.documento.mascara is not None
        # Refleja los ajustes sin volver a avisar al documento.
        self.activar.blockSignals(True)
        self.activar.setChecked(ajustes.contorno)
        self.activar.blockSignals(False)
        self.grosor.blockSignals(True)
        self.grosor.setValue(ajustes.grosor_contorno_mm)
        self.grosor.blockSignals(False)
        self.activar.setEnabled(hay_recorte)
        self.grosor.setEnabled(hay_recorte and ajustes.contorno)
        self.aviso.setVisible(not hay_recorte)
