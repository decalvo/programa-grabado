"""Panel para elegir el tipo de tramado con que se rellena cada capa tonal."""

from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox

from grabado.tramado import METODOS
from grabado.ui.documento import Documento


class PanelTramado(QGroupBox):
    def __init__(self, documento: Documento) -> None:
        super().__init__("Tramado")
        self.documento = documento

        self.metodo = QComboBox()
        for clave, metodo in METODOS.items():
            self.metodo.addItem(metodo.nombre, clave)
        self.metodo.currentIndexChanged.connect(
            lambda: documento.cambiar_ajustes(metodo_tramado=self.metodo.currentData())
        )

        layout = QFormLayout(self)
        layout.addRow("Tipo", self.metodo)

        documento.cambiado.connect(self._actualizar)
        self._actualizar()

    def _actualizar(self) -> None:
        indice = self.metodo.findData(self.documento.ajustes.metodo_tramado)
        if indice != self.metodo.currentIndex():
            self.metodo.blockSignals(True)
            self.metodo.setCurrentIndex(indice)
            self.metodo.blockSignals(False)
