"""Prueba de la ventana sin pantalla: panel de ajustes previos."""

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
    # Foto plana: tonos entre 90 y 170.
    ruta = tmp_path / "foto.png"
    Image.fromarray(np.tile(np.linspace(90, 170, 256).astype(np.uint8), (200, 1)), "L").save(ruta)
    v = Ventana()
    v.resize(900, 600)
    v.show()
    resultados = []
    v.vista_previa.procesado.connect(resultados.append)
    v.documento.cargar(ruta)
    esperar(app, lambda: resultados)
    v.resultados = resultados
    v.ruta = ruta
    yield v
    v.close()


def ultimo_con(app, ventana, condicion):
    esperar(app, lambda: condicion(ventana.resultados[-1]))
    return ventana.resultados[-1]


def test_el_panel_esta_arriba_de_los_cortes_y_parte_neutro(ventana):
    panel = ventana.panel_ajustes_previos
    assert ventana.paneles.indexOf(panel) < ventana.paneles.indexOf(ventana.panel_cortes)
    assert {c: d.value() for c, d in panel.deslizadores.items()} == {"brillo": 0, "contraste": 0, "nitidez": 0}
    assert panel.auto.isEnabled() and not panel.neutro.isEnabled()


def test_mover_el_contraste_cambia_la_vista_previa_y_los_cortes_automaticos(app, ventana):
    panel = ventana.panel_ajustes_previos
    antes = ventana.resultados[-1]
    panel.deslizadores["contraste"].setValue(80)
    assert ventana.documento.ajustes.contraste == 80
    assert panel.neutro.isEnabled()
    despues = ultimo_con(app, ventana, lambda r: r.gris.std() > 2 * antes.gris.std())
    # Los deslizadores de cortes siguen a los automáticos de la foto ajustada.
    esperar(app, lambda: [d.value() for d in ventana.panel_cortes.deslizadores]
            == [round(c) for c in despues.cortes])
    assert despues.cortes[2] - despues.cortes[0] > antes.cortes[2] - antes.cortes[0]
    # La exportación usa la foto ajustada.
    assert ventana.documento.procesar().gris.std() > 2 * np.asarray(Image.open(ventana.ruta), float).std()


def test_auto_mejorar_pone_los_deslizadores_y_neutro_los_devuelve(app, ventana):
    panel = ventana.panel_ajustes_previos
    panel.auto.click()
    ajustes = ventana.documento.ajustes
    assert ajustes.contraste > 50 and ajustes.nitidez > 0
    assert {c: d.value() for c, d in panel.deslizadores.items()} == {
        "brillo": ajustes.brillo, "contraste": ajustes.contraste, "nitidez": ajustes.nitidez}
    ultimo_con(app, ventana, lambda r: r.gris.max() - r.gris.min() > 200)
    panel.neutro.click()
    assert (ventana.documento.ajustes.brillo, ventana.documento.ajustes.contraste,
            ventana.documento.ajustes.nitidez) == (0, 0, 0)
    assert all(d.value() == 0 for d in panel.deslizadores.values())


def test_los_cortes_a_mano_se_conservan_al_ajustar(app, ventana):
    cortes = ventana.panel_cortes
    cortes.deslizadores[1].setValue(cortes.deslizadores[1].value() + 5)
    elegidos = ventana.documento.ajustes.cortes
    assert elegidos is not None
    ventana.panel_ajustes_previos.deslizadores["brillo"].setValue(30)
    assert ventana.documento.ajustes.cortes == elegidos
    resultado = ultimo_con(app, ventana, lambda r: r.gris.mean() > 150)
    assert resultado.cortes == elegidos
    assert [d.value() for d in cortes.deslizadores] == [round(c) for c in elegidos]


def test_abrir_otra_foto_vuelve_a_neutro(app, ventana):
    ventana.panel_ajustes_previos.deslizadores["nitidez"].setValue(120)
    ventana.documento.cargar(ventana.ruta)
    assert ventana.documento.ajustes.nitidez == 0
    assert ventana.panel_ajustes_previos.deslizadores["nitidez"].value() == 0
