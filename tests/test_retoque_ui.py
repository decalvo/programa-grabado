"""Prueba de la ventana sin pantalla: un trazo del pincel sobre la pestaña Foto."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from grabado.exportar import exportar
from grabado.proceso import Ajustes
from grabado.retoque import ubicar_imagen
from grabado.ui.ventana import Ventana
from grabado.ui.vista import BLANCO_DAMERO, GRIS_DAMERO

ANCHO, ALTO = 400, 300


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ventana(app, tmp_path):
    ruta = tmp_path / "foto.png"
    Image.new("RGB", (ANCHO, ALTO), (40, 30, 20)).save(ruta)
    v = Ventana()
    v.resize(1000, 700)
    v.show()
    v.documento.cargar(ruta)
    # Ajustes pequeños para que exportar sea rápido: 1 px de BMP = 1 px de foto.
    v.documento.cambiar_ajustes(ancho_mm=ANCHO / 100 * 25.4, dpi=100, cortes=(60.0, 120.0, 180.0))
    app.processEvents()
    yield v
    v.close()


def contar_cambios_de_mascara(documento, monkeypatch):
    llamadas = []
    original = documento.cambiar_mascara

    def contar(mascara):
        llamadas.append(mascara)
        original(mascara)

    monkeypatch.setattr(documento, "cambiar_mascara", contar)
    return llamadas


def a_widget(capa, x, y):
    """Centro del píxel (x, y) de la foto en coordenadas de la capa del pincel."""
    izquierda, arriba, ancho, alto = ubicar_imagen((ANCHO, ALTO), (capa.width(), capa.height()))
    return QPoint(round(izquierda + (x + 0.5) * ancho / ANCHO), round(arriba + (y + 0.5) * alto / ALTO))


def trazar(capa, puntos):
    QTest.mousePress(capa, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, puntos[0])
    for punto in puntos[1:]:
        QTest.mouseMove(capa, punto)
    # Mientras se arrastra, el trazo se dibuja en pantalla sin tocar la máscara.
    assert not capa.grab().isNull()
    QTest.mouseRelease(capa, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, puntos[-1])


def test_un_trazo_borra_con_un_solo_cambio_y_se_exporta(app, ventana, tmp_path, monkeypatch):
    panel = ventana.panel_retoque
    documento = ventana.documento
    assert documento.mascara is None
    llamadas = contar_cambios_de_mascara(documento, monkeypatch)

    panel.activo.setChecked(True)
    assert ventana.pestanas.currentWidget() is ventana.vista
    capa = panel.capa
    assert capa.isVisible() and capa.size() == ventana.vista.size()
    escala = capa.width() / ANCHO if capa.width() / ANCHO < capa.height() / ALTO else capa.height() / ALTO
    panel.tamano.setValue(round(20 * escala))  # unos 20 px de la foto

    trazar(capa, [a_widget(capa, x, 150) for x in range(100, 301, 20)])

    assert len(llamadas) == 1
    mascara = np.asarray(documento.mascara)
    assert mascara.shape == (ALTO, ANCHO)
    assert (mascara[150, 100:301] == 0).all()
    assert (mascara[130, :] == 255).all() and (mascara[:, 50] == 255).all()

    # La pestaña Foto muestra el damero donde se borró.
    vista = np.asarray(ventana.vista._imagen)
    assert tuple(vista[150, 200]) in {GRIS_DAMERO, BLANCO_DAMERO}
    assert tuple(vista[50, 50]) == (40, 30, 20)

    # Los BMP exportados no graban la zona borrada y sí el resto del sujeto.
    exportar(documento.procesar(), tmp_path, "foto")
    grabado = np.zeros((ALTO, ANCHO), bool)
    for nombre in ("foto_1_negro.bmp", "foto_2_oscuro.bmp", "foto_3_medio.bmp"):
        with Image.open(tmp_path / nombre) as bmp:
            assert bmp.size == (ANCHO, ALTO)
            grabado |= np.asarray(bmp.convert("L")) == 0
    assert not grabado[145:156, 110:291].any()
    assert grabado[:100].mean() > 0.5

    # Deshacer (botón) vuelve a la foto sin retocar.
    assert panel.deshacer.isEnabled()
    panel.deshacer.click()
    assert documento.mascara is None
    assert not panel.deshacer.isEnabled()


def test_recuperar_devuelve_la_foto_de_origen(app, ventana, monkeypatch):
    documento = ventana.documento
    documento.cambiar_mascara(Image.new("L", (ANCHO, ALTO), 0))  # todo fondo
    panel = ventana.panel_retoque
    panel.activo.setChecked(True)
    panel.recuperar.setChecked(True)
    llamadas = contar_cambios_de_mascara(documento, monkeypatch)

    capa = panel.capa
    trazar(capa, [a_widget(capa, 200, 100), a_widget(capa, 200, 200)])

    assert len(llamadas) == 1
    assert (np.asarray(documento.mascara)[100:201, 200] == 255).all()
    assert tuple(np.asarray(ventana.vista._imagen)[150, 200]) == (40, 30, 20)

    # Ctrl+Z deshace el trazo.
    QTest.keyClick(ventana, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert (np.asarray(documento.mascara) == 0).all()


def test_pincel_desactivado_sin_foto(app):
    v = Ventana()
    panel = v.panel_retoque
    assert not panel.activo.isEnabled()
    assert not panel.deshacer.isEnabled()
    panel.activo.setChecked(True)
    assert not panel.capa.isVisible()
    v.close()


def test_exportar_tambien_con_ajustes_por_defecto(app, ventana):
    # El retoque se aplica a la máscara de resolución completa: vale para cualquier tamaño final.
    panel = ventana.panel_retoque
    panel.activo.setChecked(True)
    capa = panel.capa
    trazar(capa, [a_widget(capa, 200, 150)])
    resultado = ventana.documento.procesar(Ajustes(ancho_mm=50, dpi=254))
    alto, ancho = resultado.mascara.shape
    assert not resultado.mascara[alto // 2, ancho // 2]
    assert resultado.mascara[5, 5]
