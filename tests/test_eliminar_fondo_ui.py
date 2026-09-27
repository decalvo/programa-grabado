import os
import threading

import numpy as np
import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox  # noqa: E402

from grabado.ui.documento import Documento  # noqa: E402
from grabado.ui.eliminar_fondo import EliminarFondo  # noqa: E402
from grabado.ui.vista import BLANCO_DAMERO, GRIS_DAMERO, componer_recorte  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def foto(ancho=60, alto=40, color=(10, 80, 150)):
    return Image.new("RGB", (ancho, alto), color)


def mascara_centro(imagen):
    datos = np.zeros((imagen.height, imagen.width), np.uint8)
    datos[10:30, 20:40] = 255
    return Image.fromarray(datos, "L")


class RecortadorFalso:
    dispositivo = "CPU"

    def __init__(self, error=None):
        self.error = error
        self.hilo = None
        self.puede_terminar = threading.Event()
        self.puede_terminar.set()

    def __call__(self, imagen):
        self.hilo = threading.current_thread()
        self.puede_terminar.wait(5)
        if self.error:
            raise self.error
        return mascara_centro(imagen)


def preparar(app, recortador):
    ventana = QMainWindow()
    documento = Documento()
    accion = EliminarFondo(ventana, documento, recortador)
    return ventana, documento, accion


def esperar(accion):
    bucle = QEventLoop()
    accion.listo.connect(bucle.quit)
    QTimer.singleShot(5000, bucle.quit)
    bucle.exec()


def test_boton_desactivado_sin_foto(app):
    _, documento, accion = preparar(app, RecortadorFalso())
    assert not accion.accion.isEnabled()
    documento.foto = foto()
    documento.cambiado.emit()
    assert accion.accion.isEnabled()


def test_genera_la_mascara_fuera_del_hilo_de_la_ventana(app):
    recortador = RecortadorFalso()
    recortador.puede_terminar.clear()
    _, documento, accion = preparar(app, recortador)
    documento.foto = foto()
    documento.cambiado.emit()

    accion.accion.trigger()
    assert accion.ocupado and not accion.accion.isEnabled()
    recortador.puede_terminar.set()
    esperar(accion)

    assert recortador.hilo is not threading.main_thread()
    assert documento.mascara is not None
    assert np.asarray(documento.mascara)[20, 30] == 255
    assert not accion.ocupado and accion.accion.isEnabled()


def test_si_cambia_la_foto_no_aplica_la_mascara_vieja(app):
    recortador = RecortadorFalso()
    recortador.puede_terminar.clear()
    _, documento, accion = preparar(app, recortador)
    documento.foto = foto()
    accion.ejecutar()
    documento.foto = foto(color=(1, 2, 3))
    recortador.puede_terminar.set()
    esperar(accion)
    assert documento.mascara is None


def test_error_se_avisa_sin_romper(app, monkeypatch):
    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: avisos.append(args))
    _, documento, accion = preparar(app, RecortadorFalso(RuntimeError("sin modelo")))
    documento.foto = foto()
    accion.ejecutar()
    esperar(accion)
    assert documento.mascara is None
    assert "sin modelo" in avisos[0][2]
    assert accion.accion.isEnabled()


def test_recorte_distingue_el_fondo(app):
    imagen = foto()
    recorte = np.asarray(componer_recorte(imagen, mascara_centro(imagen)))
    assert tuple(recorte[20, 30]) == (10, 80, 150)
    fondo = {tuple(p) for p in recorte[:10].reshape(-1, 3)}
    assert fondo <= {GRIS_DAMERO, BLANCO_DAMERO}
    assert len(fondo) == 2
