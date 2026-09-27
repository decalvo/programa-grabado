"""Panel de ajustes previos: brillo, contraste y nitidez del sujeto, auto-mejorar y volver a neutro."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout

from grabado import ajustes_previos as ap
from grabado.ui.documento import Documento

# (campo de Ajustes, nombre, mínimo, máximo, ayuda)
CONTROLES = (
    ("brillo", "Brillo", ap.BRILLO_MIN, ap.BRILLO_MAX, "Aclara (+) u oscurece (−) el sujeto"),
    ("contraste", "Contraste", ap.CONTRASTE_MIN, ap.CONTRASTE_MAX,
     "Separa (+) o junta (−) los tonos claros y oscuros del sujeto"),
    ("nitidez", "Nitidez", ap.NITIDEZ_MIN, ap.NITIDEZ_MAX,
     f"Realza el detalle fino (de unos {ap.RADIO_NITIDEZ_MM:g} mm) como ojos, pelo y bordes"),
)

NEUTROS = {campo: 0 for campo, *_ in CONTROLES}


class PanelAjustesPrevios(QGroupBox):
    def __init__(self, documento: Documento) -> None:
        super().__init__("Ajustes previos")
        self.documento = documento

        rejilla = QGridLayout()
        self.deslizadores: dict[str, QSlider] = {}
        self.valores: dict[str, QLabel] = {}
        for fila, (campo, nombre, minimo, maximo, ayuda) in enumerate(CONTROLES):
            deslizador = QSlider(Qt.Orientation.Horizontal)
            deslizador.setRange(minimo, maximo)
            deslizador.setToolTip(ayuda)
            deslizador.valueChanged.connect(lambda v, campo=campo: self._mover(campo, v))
            valor = QLabel()
            valor.setMinimumWidth(28)
            valor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            rejilla.addWidget(QLabel(nombre), 2 * fila, 0, 1, 2)
            rejilla.addWidget(deslizador, 2 * fila + 1, 0)
            rejilla.addWidget(valor, 2 * fila + 1, 1)
            self.deslizadores[campo] = deslizador
            self.valores[campo] = valor

        self.auto = QPushButton("Auto-mejorar")
        self.auto.setToolTip("Estira los tonos del sujeto a casi toda la gama y realza un poco la nitidez")
        self.auto.clicked.connect(self._auto_mejorar)
        self.neutro = QPushButton("Neutro")
        self.neutro.setToolTip("Vuelve brillo, contraste y nitidez a 0 (la foto tal cual)")
        self.neutro.clicked.connect(lambda: documento.cambiar_ajustes(**NEUTROS))
        botones = QHBoxLayout()
        botones.addWidget(self.auto)
        botones.addWidget(self.neutro)

        layout = QVBoxLayout(self)
        layout.addLayout(rejilla)
        layout.addLayout(botones)

        documento.cambiado.connect(self._actualizar)
        self._actualizar()

    def _mover(self, campo: str, valor: int) -> None:
        self.valores[campo].setText(str(valor))
        self.documento.cambiar_ajustes(**{campo: valor})

    def _auto_mejorar(self) -> None:
        doc = self.documento
        if doc.foto is not None:
            doc.cambiar_ajustes(**ap.auto_mejorar_foto(doc.foto, doc.mascara))

    def _actualizar(self) -> None:
        doc = self.documento
        for campo, deslizador in self.deslizadores.items():
            deslizador.setEnabled(doc.tiene_foto)
            valor = getattr(doc.ajustes, campo)
            if deslizador.value() != valor:
                deslizador.blockSignals(True)
                deslizador.setValue(valor)
                deslizador.blockSignals(False)
            self.valores[campo].setText(str(valor))
        self.auto.setEnabled(doc.tiene_foto)
        self.neutro.setEnabled(doc.tiene_foto and any(getattr(doc.ajustes, c) for c in NEUTROS))
