"""Panel de cortes tonales: tres deslizadores que no se cruzan y un botón para volver a los automáticos."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QPushButton, QSlider, QVBoxLayout

from grabado.proceso import Resultado
from grabado.tonal import Cortes, mover_corte
from grabado.ui.documento import Documento

NOMBRES = ("Negro / Oscuro", "Oscuro / Medio", "Medio / Claro")


class PanelCortes(QGroupBox):
    def __init__(self, documento: Documento) -> None:
        super().__init__("Cortes tonales")
        self.documento = documento
        # Cortes que muestran los deslizadores: los elegidos o, si son automáticos,
        # los que usó la última vista previa.
        self._cortes: Cortes | None = None

        rejilla = QGridLayout()
        self.deslizadores: list[QSlider] = []
        self.valores: list[QLabel] = []
        for i, nombre in enumerate(NOMBRES):
            deslizador = QSlider(Qt.Orientation.Horizontal)
            deslizador.setRange(0, 255)
            deslizador.setToolTip("Tono donde termina una capa y empieza la siguiente (0 = negro, 255 = blanco)")
            deslizador.valueChanged.connect(lambda v, i=i: self._mover(i, v))
            valor = QLabel()
            valor.setMinimumWidth(28)
            valor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            rejilla.addWidget(QLabel(nombre), 2 * i, 0, 1, 2)
            rejilla.addWidget(deslizador, 2 * i + 1, 0)
            rejilla.addWidget(valor, 2 * i + 1, 1)
            self.deslizadores.append(deslizador)
            self.valores.append(valor)

        self.estado = QLabel()
        self.estado.setWordWrap(True)
        self.automatico = QPushButton("Automático")
        self.automatico.setToolTip("Vuelve a repartir las capas por cantidad de píxeles")
        self.automatico.clicked.connect(lambda: documento.cambiar_ajustes(cortes=None))

        layout = QVBoxLayout(self)
        layout.addLayout(rejilla)
        layout.addWidget(self.estado)
        layout.addWidget(self.automatico)

        documento.cambiado.connect(self._actualizar)
        self._actualizar()

    def mostrar_resultado(self, resultado: Resultado) -> None:
        """Coloca los deslizadores en los cortes automáticos que usó la vista previa."""
        if self.documento.ajustes.cortes is None:
            self._mostrar(resultado.cortes)

    def _actualizar(self) -> None:
        doc = self.documento
        for deslizador in self.deslizadores:
            deslizador.setEnabled(doc.tiene_foto)
        manual = doc.ajustes.cortes is not None
        self.automatico.setEnabled(doc.tiene_foto and manual)
        self.estado.setText("Cortes elegidos a mano." if manual else "Cortes automáticos.")
        if manual:
            self._mostrar(doc.ajustes.cortes)
        elif not doc.tiene_foto:
            self._cortes = None

    def _mostrar(self, cortes: Cortes) -> None:
        self._cortes = cortes
        for deslizador, valor, corte in zip(self.deslizadores, self.valores, cortes):
            deslizador.blockSignals(True)
            deslizador.setValue(round(corte))
            deslizador.blockSignals(False)
            valor.setText(str(round(corte)))

    def _mover(self, indice: int, valor: int) -> None:
        if self._cortes is None:
            return
        # Se parte de lo que muestran los deslizadores, para que se use lo que se ve.
        mostrados = tuple(float(round(c)) for c in self._cortes)
        nuevos = mover_corte(mostrados, indice, valor)
        # Si chocó con un vecino, el deslizador vuelve al tope; si no, cambia solo el que se movió.
        self._mostrar(nuevos)
        self.documento.cambiar_ajustes(cortes=nuevos)
