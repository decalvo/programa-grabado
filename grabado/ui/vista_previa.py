"""Vista previa del grabado en madera, recalculada en segundo plano a la resolución de la pantalla."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from PIL import Image
from PySide6.QtCore import QTimer, Signal

from grabado.proceso import Ajustes, Resultado, procesar, tamano_final_px
from grabado.simulacion import dpi_para_caja, simular
from grabado.ui.documento import Documento
from grabado.ui.vista import VistaImagen

# Espera tras el último cambio antes de recalcular, para no encolar trabajo mientras se arrastra.
ESPERA_MS = 30

TEXTO_VACIO = "Abre una foto para ver la vista previa"


class VistaPrevia(VistaImagen):
    # Resultado de la última vista previa calculada (a resolución reducida).
    procesado = Signal(object)
    _terminado = Signal(int, object, object)

    def __init__(self, documento: Documento) -> None:
        super().__init__(TEXTO_VACIO)
        self.documento = documento
        self._hilo = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vista-previa")
        self._pedido = 0  # número del último pedido
        self._ocupado = False
        self._pendiente: tuple | None = None
        self._reducida: tuple | None = None  # (clave, foto, mascara) ya reducidas

        self._espera = QTimer(self)
        self._espera.setSingleShot(True)
        self._espera.setInterval(ESPERA_MS)
        self._espera.timeout.connect(self._pedir)

        self._terminado.connect(self._al_terminar)
        documento.cambiado.connect(self._espera.start)
        self.destroyed.connect(lambda: self._hilo.shutdown(wait=False, cancel_futures=True))

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        self._espera.start()

    def _pedir(self) -> None:
        doc = self.documento
        self._pedido += 1
        if doc.foto is None:
            self.mostrar(None)
            self.setText(TEXTO_VACIO)
            return
        escala = self.devicePixelRatioF()
        caja = (max(1, round(self.width() * escala)), max(1, round(self.height() * escala)))
        self._pendiente = (self._pedido, doc.foto, doc.mascara, doc.ajustes, caja)
        self._lanzar()

    def _lanzar(self) -> None:
        # Un solo cálculo a la vez; si llegan varios pedidos mientras tanto, solo se hace el último.
        if self._ocupado or self._pendiente is None:
            return
        pedido, self._pendiente = self._pendiente, None
        self._ocupado = True
        self._hilo.submit(self._calcular, *pedido)

    def _calcular(self, numero, foto, mascara, ajustes: Ajustes, caja) -> None:
        try:
            resultado = self._procesar_reducido(foto, mascara, ajustes, caja)
            self._terminado.emit(numero, resultado, simular(resultado))
        except Exception as error:  # noqa: BLE001 - se informa en el hilo principal
            self._terminado.emit(numero, None, error)

    def _procesar_reducido(self, foto, mascara, ajustes: Ajustes, caja) -> Resultado:
        dpi = dpi_para_caja(foto.size, ajustes.ancho_mm, ajustes.dpi, caja)
        tamano = tamano_final_px(foto.size, ajustes.ancho_mm, dpi)
        # Reducir una foto grande es lo más lento; se hace una vez por foto, máscara y tamaño.
        # Solo el hilo de trabajo toca esta caché.
        g = self._reducida
        if g is None or g[0] is not foto or g[1] is not mascara or g[2] != tamano:
            # Tras un trazo de retoque solo cambia la máscara: la foto reducida se reutiliza.
            if g is not None and g[0] is foto and g[2] == tamano:
                foto_r = g[3]
            else:
                foto_r = foto.resize(tamano, Image.Resampling.LANCZOS)
            mascara_r = None
            if mascara is not None:
                mascara_r = mascara.convert("L").resize(tamano, Image.Resampling.BILINEAR)
            g = self._reducida = (foto, mascara, tamano, foto_r, mascara_r)
        return procesar(g[3], replace(ajustes, dpi=dpi), g[4])

    def _al_terminar(self, numero: int, resultado, imagen) -> None:
        self._ocupado = False
        self._lanzar()
        if numero != self._pedido:
            return  # ya hay un pedido más nuevo
        if resultado is None:
            self.mostrar(None)
            self.setText(f"No se pudo calcular la vista previa:\n{imagen}")
            return
        self.mostrar(imagen)
        self.procesado.emit(resultado)
