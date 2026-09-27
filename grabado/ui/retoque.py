"""Retoque del recorte con pincel sobre la pestaña "Foto".

Mientras se arrastra, el trazo se dibuja solo en pantalla (sobre la imagen ya escalada);
al soltar, se aplica una vez a la máscara a resolución completa y se guarda en el documento.
Así la vista previa se recalcula una sola vez por trazo.
"""

from PIL import Image
from PySide6.QtCore import QEvent, QObject, QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QKeySequence, QPainter, QPainterPath, QPen, QPixmap, QShortcut, QTransform
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from grabado import retoque
from grabado.ui.documento import Documento
from grabado.ui.vista import BLANCO_DAMERO, GRIS_DAMERO, a_qimage, casilla_damero

# Diámetro del pincel en píxeles de pantalla.
TAMANO_MINIMO = 2
TAMANO_MAXIMO = 200
TAMANO_INICIAL = 30


class CapaRetoque(QWidget):
    """Capa transparente sobre la vista de la foto que recibe el ratón y dibuja el pincel."""

    # Puntos del trazo en coordenadas de la foto y radio en píxeles de la foto.
    trazo_terminado = Signal(list, float)

    def __init__(self, vista: QWidget, documento: Documento) -> None:
        super().__init__(vista)
        self.documento = documento
        self.modo = retoque.BORRAR
        self.diametro = TAMANO_INICIAL
        self._cursor: QPointF | None = None
        self._trazo: list[QPointF] = []
        self._textura_foto: tuple | None = None  # (foto, tamaño, pixmap) para "Recuperar"
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(vista.rect())
        vista.installEventFilter(self)
        self.hide()

    def eventFilter(self, objeto: QObject, evento: QEvent) -> bool:
        if objeto is self.parent() and evento.type() == QEvent.Type.Resize:
            self.setGeometry(self.parent().rect())
        return False

    # --- Geometría -------------------------------------------------------------------

    def _tamano_widget(self) -> tuple[int, int]:
        return self.width(), self.height()

    def _escala(self) -> float:
        return retoque.escala_en_pantalla(self.documento.foto.size, self._tamano_widget())

    def a_imagen(self, punto: QPointF) -> retoque.Punto:
        return retoque.widget_a_imagen((punto.x(), punto.y()), self.documento.foto.size, self._tamano_widget())

    # --- Ratón -----------------------------------------------------------------------

    def mousePressEvent(self, evento) -> None:
        if evento.button() != Qt.MouseButton.LeftButton or self.documento.foto is None:
            return
        self._trazo = [evento.position()]
        self._cursor = evento.position()
        self.update()

    def mouseMoveEvent(self, evento) -> None:
        self._cursor = evento.position()
        if self._trazo:
            self._trazo.append(evento.position())
        self.update()

    def mouseReleaseEvent(self, evento) -> None:
        if evento.button() != Qt.MouseButton.LeftButton or not self._trazo:
            return
        trazo, self._trazo = self._trazo, []
        if self.documento.foto is not None:
            escala = self._escala()
            if escala > 0:
                puntos = [self.a_imagen(p) for p in trazo]
                self.trazo_terminado.emit(puntos, self.diametro / 2 / escala)
        self.update()

    def leaveEvent(self, evento) -> None:
        self._cursor = None
        self.update()

    def hideEvent(self, evento) -> None:
        self._trazo = []
        self._cursor = None

    # --- Dibujo ----------------------------------------------------------------------

    def _pincel_de_relleno(self) -> QBrush:
        """Cómo se verá lo pintado: damero si se borra, la foto de origen si se recupera."""
        foto = self.documento.foto
        x, y, ancho, alto = retoque.ubicar_imagen(foto.size, self._tamano_widget())
        escala = ancho / foto.width
        if self.modo == retoque.BORRAR:
            casilla = casilla_damero(foto.size)
            baldosa = QPixmap(2 * casilla, 2 * casilla)
            baldosa.fill(QColor(*BLANCO_DAMERO))
            pintor = QPainter(baldosa)
            pintor.fillRect(0, 0, casilla, casilla, QColor(*GRIS_DAMERO))
            pintor.fillRect(casilla, casilla, casilla, casilla, QColor(*GRIS_DAMERO))
            pintor.end()
            pincel = QBrush(baldosa)
            pincel.setTransform(QTransform.fromTranslate(x, y).scale(escala, escala))
            return pincel
        # La foto reducida al tamaño en pantalla se prepara una vez por foto y tamaño.
        guardada = self._textura_foto
        if guardada is None or guardada[0] is not foto or guardada[1] != (ancho, alto):
            reducida = foto.convert("RGB").resize((max(1, ancho), max(1, alto)), Image.Resampling.BILINEAR)
            guardada = self._textura_foto = (foto, (ancho, alto), QPixmap.fromImage(a_qimage(reducida)))
        pincel = QBrush(guardada[2])
        pincel.setTransform(QTransform.fromTranslate(x, y))
        return pincel

    def paintEvent(self, evento) -> None:
        if self.documento.foto is None:
            return
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._trazo:
            camino = QPainterPath(self._trazo[0])
            for punto in self._trazo[1:]:
                camino.lineTo(punto)
            if len(self._trazo) == 1:
                camino.lineTo(self._trazo[0] + QPointF(0.01, 0))
            lapiz = QPen(self._pincel_de_relleno(), self.diametro)
            lapiz.setCapStyle(Qt.PenCapStyle.RoundCap)
            lapiz.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            pintor.strokePath(camino, lapiz)
        if self._cursor is not None:
            radio = self.diametro / 2
            pintor.setBrush(Qt.BrushStyle.NoBrush)
            pintor.setPen(QPen(QColor(0, 0, 0, 200), 1.5))
            pintor.drawEllipse(self._cursor, radio, radio)
            pintor.setPen(QPen(QColor(255, 255, 255, 200), 1, Qt.PenStyle.DashLine))
            pintor.drawEllipse(self._cursor, radio, radio)
        pintor.end()


class PanelRetoque(QGroupBox):
    """Controles del pincel: activar, modo, tamaño y deshacer."""

    # Se emite al activar el pincel, para mostrar la pestaña "Foto".
    activado = Signal()

    def __init__(self, documento: Documento, vista: QWidget) -> None:
        super().__init__("Retoque")
        self.documento = documento
        self.retoque = retoque.Retoque()
        self.capa = CapaRetoque(vista, documento)
        self.capa.trazo_terminado.connect(self._aplicar)

        self.activo = QCheckBox("Pincel")
        self.activo.setToolTip("Pinta sobre la pestaña Foto para corregir el recorte")
        self.activo.toggled.connect(self._activar)

        self.borrar = QRadioButton("Borrar")
        self.borrar.setToolTip("Lo que se pinta pasa a ser fondo")
        self.recuperar = QRadioButton("Recuperar")
        self.recuperar.setToolTip("Lo que se pinta vuelve a ser parte del sujeto")
        self.borrar.setChecked(True)
        self._modos = QButtonGroup(self)
        self._modos.addButton(self.borrar)
        self._modos.addButton(self.recuperar)
        self._modos.buttonToggled.connect(self._cambiar_modo)
        modos = QHBoxLayout()
        modos.addWidget(self.borrar)
        modos.addWidget(self.recuperar)

        self.tamano = QSlider(Qt.Orientation.Horizontal)
        self.tamano.setRange(TAMANO_MINIMO, TAMANO_MAXIMO)
        self.tamano.setValue(TAMANO_INICIAL)
        self.tamano.setToolTip("Diámetro del pincel en pantalla")
        self.tamano.valueChanged.connect(self._cambiar_tamano)

        self.deshacer = QPushButton("Deshacer trazo")
        self.deshacer.setToolTip("Ctrl+Z")
        self.deshacer.clicked.connect(self._deshacer)
        atajo = QShortcut(QKeySequence.StandardKey.Undo, vista)
        atajo.setContext(Qt.ShortcutContext.WindowShortcut)
        atajo.activated.connect(self._deshacer)

        formulario = QFormLayout()
        formulario.addRow("Tamaño", self.tamano)
        layout = QVBoxLayout(self)
        layout.addWidget(self.activo)
        layout.addLayout(modos)
        layout.addLayout(formulario)
        layout.addWidget(self.deshacer)

        documento.cambiado.connect(self._actualizar)
        self._actualizar()

    def _activar(self, activo: bool) -> None:
        self.capa.setVisible(activo and self.documento.tiene_foto)
        if activo:
            self.capa.raise_()
            self.activado.emit()

    def _cambiar_modo(self) -> None:
        self.capa.modo = retoque.BORRAR if self.borrar.isChecked() else retoque.RECUPERAR

    def _cambiar_tamano(self, valor: int) -> None:
        self.capa.diametro = valor
        self.capa.update()

    def _aplicar(self, puntos: list, radio: float) -> None:
        doc = self.documento
        if doc.foto is None:
            return
        nueva = self.retoque.trazar(doc.foto, doc.mascara, puntos, radio, self.capa.modo)
        if nueva is not None:
            doc.cambiar_mascara(nueva)

    def _deshacer(self) -> None:
        if self.retoque.puede_deshacer(self.documento.mascara):
            self.documento.cambiar_mascara(self.retoque.deshacer(self.documento.mascara))

    def _actualizar(self) -> None:
        tiene_foto = self.documento.tiene_foto
        for control in (self.activo, self.borrar, self.recuperar, self.tamano):
            control.setEnabled(tiene_foto)
        self.capa.setVisible(tiene_foto and self.activo.isChecked())
        self.deshacer.setEnabled(self.retoque.puede_deshacer(self.documento.mascara))
