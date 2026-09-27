"""Prueba de la ventana sin pantalla: deslizadores de cortes tonales y vista previa."""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from grabado.ui.ventana import Ventana


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def esperar(app, condicion, segundos=10.0):
    limite = time.monotonic() + segundos
    while not condicion():
        assert time.monotonic() < limite, "tiempo agotado"
        app.processEvents()
        time.sleep(0.005)


@pytest.fixture
def ventana(app, tmp_path):
    ruta = tmp_path / "foto.png"
    Image.fromarray(np.tile(np.arange(256, dtype=np.uint8), (200, 1)), "L").save(ruta)
    v = Ventana()
    v.resize(900, 600)
    v.show()
    resultados = []
    v.vista_previa.procesado.connect(resultados.append)
    v.documento.cargar(ruta)
    esperar(app, lambda: resultados)
    v.resultados = resultados
    yield v
    v.close()


def valores(panel):
    return [d.value() for d in panel.deslizadores]


def test_al_cargar_los_deslizadores_estan_en_los_cortes_automaticos(ventana):
    panel = ventana.panel_cortes
    assert ventana.documento.ajustes.cortes is None
    automaticos = ventana.documento.procesar().cortes
    assert valores(panel) == pytest.approx([round(c) for c in automaticos], abs=1)
    assert not panel.automatico.isEnabled()
    assert ventana.vista_previa.pixmap() is not None and not ventana.vista_previa.pixmap().isNull()


def test_mover_un_deslizador_guarda_los_cortes_y_no_cruza(app, ventana):
    panel = ventana.panel_cortes
    c0, c1, c2 = valores(panel)
    panel.deslizadores[0].setValue(c1 + 30)
    cortes = ventana.documento.ajustes.cortes
    assert cortes == (c1 - 1, c1, c2)
    assert valores(panel)[0] == c1 - 1
    # La exportación usa los cortes elegidos.
    assert ventana.documento.procesar().cortes == cortes
    n = len(ventana.resultados)
    esperar(app, lambda: len(ventana.resultados) > n and ventana.resultados[-1].cortes == cortes)


def test_automatico_devuelve_los_deslizadores(app, ventana):
    panel = ventana.panel_cortes
    inicial = valores(panel)
    panel.deslizadores[1].setValue(inicial[1] - 20)
    assert panel.automatico.isEnabled()
    panel.automatico.click()
    assert ventana.documento.ajustes.cortes is None
    esperar(app, lambda: valores(panel) == inicial)
