"""Prueba de la ventana sin pantalla: guardar un proyecto, reabrirlo y exportar lo mismo."""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from grabado import proyecto
from grabado.proceso import Ajustes
from grabado.ui.ventana import Ventana
from tests.test_proyecto import foto_jpeg_girada, mascara_suave

AJUSTES = Ajustes(
    ancho_mm=42.5,
    dpi=150,
    cortes=(55.0, 110.0, 180.0),
    metodo_tramado="stucki",
    brillo=-8,
    contraste=30,
    nitidez=25,
    contorno=True,
    grosor_contorno_mm=1.5,
)


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
def ventanas(app):
    creadas = []

    def crear():
        v = Ventana()
        v.resize(1000, 700)
        v.show()
        creadas.append(v)
        return v

    yield crear
    for v in creadas:
        v.close()


@pytest.fixture
def ruta_foto(tmp_path):
    return foto_jpeg_girada(tmp_path / "Luna.jpg")


def responder(monkeypatch, **respuestas):
    """Reemplaza los diálogos: cada uno devuelve lo indicado (o falla si no se esperaba)."""
    for nombre, valor in respuestas.items():
        clase = QMessageBox if nombre in ("question", "information", "warning") else QFileDialog
        if isinstance(valor, Exception):
            def lanzar(*a, _error=valor, **k):
                raise _error
            monkeypatch.setattr(clase, nombre, lanzar)
        else:
            monkeypatch.setattr(clase, nombre, lambda *a, _v=valor, **k: _v)


def trabajo_completo(app, v, ruta_foto):
    doc = v.documento
    doc.cargar(ruta_foto)
    doc.cambiar_mascara(mascara_suave(doc.foto.size))
    doc.cambiar_ajustes(**{c: getattr(AJUSTES, c) for c in AJUSTES.__dataclass_fields__})
    # Un trazo de retoque, para tener algo que deshacer.
    v.panel_retoque._aplicar([(80.0, 120.0)], 6.0)
    assert v.panel_retoque.deshacer.isEnabled()
    app.processEvents()


def exportar_con_panel(monkeypatch, v, carpeta):
    responder(monkeypatch, getExistingDirectory=str(carpeta), information=None)
    v.panel_exportar.boton.click()
    return {p.name: p.read_bytes() for p in sorted(carpeta.iterdir())}


def test_guardar_abrir_y_exportar_da_los_mismos_bmp(app, ventanas, ruta_foto, tmp_path, monkeypatch):
    v = ventanas()
    trabajo_completo(app, v, ruta_foto)
    assert v.documento.modificado and v.isWindowModified()
    assert "Luna.jpg" in v.windowTitle()

    # La primera vez pregunta dónde; la extensión se agrega sola.
    responder(monkeypatch, getSaveFileName=(str(tmp_path / "trabajo"), proyecto.FILTRO))
    v.accion_guardar.trigger()
    ruta = tmp_path / "trabajo.grabado"
    assert ruta.exists()
    assert not v.documento.modificado and not v.isWindowModified()
    assert v.windowTitle().startswith("trabajo[*]")
    antes = exportar_con_panel(monkeypatch, v, tmp_path / "antes")
    assert "Luna_4_contorno.bmp" in antes

    otra = ventanas()
    otra.eliminar_fondo.ejecutar = lambda: pytest.fail("no debe volver a eliminar el fondo")
    resultados = []
    otra.vista_previa.procesado.connect(resultados.append)
    responder(monkeypatch, getOpenFileName=(str(ruta), proyecto.FILTRO))
    otra.accion_abrir_proyecto.trigger()
    esperar(app, lambda: resultados)

    doc = otra.documento
    assert doc.ajustes == v.documento.ajustes
    assert np.array_equal(np.asarray(doc.mascara), np.asarray(v.documento.mascara))
    assert np.array_equal(np.asarray(doc.foto), np.asarray(v.documento.foto))
    assert doc.ruta.name == "Luna.jpg" and doc.ruta_proyecto == ruta
    assert not doc.modificado and not otra.isWindowModified()
    assert otra.windowTitle().startswith("trabajo[*]")

    # Cada panel muestra lo restaurado.
    previos = otra.panel_ajustes_previos
    assert {c: d.value() for c, d in previos.deslizadores.items()} == {"brillo": -8, "contraste": 30, "nitidez": 25}
    assert [d.value() for d in otra.panel_cortes.deslizadores] == [55, 110, 180]
    assert otra.panel_cortes.estado.text() == "Cortes elegidos a mano."
    assert otra.panel_tramado.metodo.currentData() == "stucki"
    assert otra.panel_contorno.activar.isChecked() and otra.panel_contorno.activar.isEnabled()
    assert otra.panel_contorno.grosor.value() == 1.5
    assert otra.panel_exportar.ancho.value() == 42.5
    assert otra.panel_exportar.dpi.value() == 150

    despues = exportar_con_panel(monkeypatch, otra, tmp_path / "despues")
    assert despues == antes


def test_ctrl_s_guarda_en_el_mismo_archivo_sin_preguntar(app, ventanas, ruta_foto, tmp_path, monkeypatch):
    v = ventanas()
    v.documento.cargar(ruta_foto)
    ruta = tmp_path / "p.grabado"
    v.documento.guardar_proyecto(ruta)
    v.documento.cambiar_ajustes(brillo=20)
    assert v.isWindowModified()
    responder(monkeypatch, getSaveFileName=AssertionError("no debe preguntar"))
    assert v.guardar()
    assert proyecto.abrir(ruta).ajustes.brillo == 20
    assert not v.isWindowModified()


def test_abrir_un_proyecto_olvida_el_historial_de_retoque(app, ventanas, ruta_foto, tmp_path, monkeypatch):
    v = ventanas()
    v.documento.cargar(ruta_foto)
    ruta = tmp_path / "p.grabado"
    v.documento.guardar_proyecto(ruta)
    trabajo_completo(app, v, ruta_foto)
    responder(monkeypatch, question=QMessageBox.StandardButton.Discard,
              getOpenFileName=(str(ruta), proyecto.FILTRO))
    v.accion_abrir_proyecto.trigger()
    assert v.documento.mascara is None
    assert not v.panel_retoque.deshacer.isEnabled()


def test_abrir_la_foto_recien_abierta_no_esta_modificada(app, ventanas, ruta_foto):
    v = ventanas()
    resultados = []
    v.vista_previa.procesado.connect(resultados.append)
    assert not v.accion_guardar.isEnabled()
    v.documento.cambiar_ajustes(dpi=300)  # sin foto (p. ej. para la plantilla de calibración)
    assert not v.documento.modificado
    v.documento.cargar(ruta_foto)
    esperar(app, lambda: resultados)
    assert v.accion_guardar.isEnabled()
    assert not v.documento.modificado and v.windowTitle().startswith("Luna.jpg[*]")


def test_cambios_sin_guardar_preguntan_antes_de_perderse(app, ventanas, ruta_foto, tmp_path, monkeypatch):
    v = ventanas()
    v.documento.cargar(ruta_foto)
    v.documento.cambiar_ajustes(nitidez=50)

    # Cancelar: no se abre nada.
    responder(monkeypatch, question=QMessageBox.StandardButton.Cancel,
              getOpenFileName=AssertionError("no debe abrir"))
    v.accion_abrir_proyecto.trigger()
    assert v.documento.ajustes.nitidez == 50 and v.documento.modificado

    # Cerrar y cancelar: la ventana sigue abierta.
    v.close()
    assert v.isVisible()

    # Guardar: primero pregunta dónde guardar y después sigue abriendo.
    otra_foto = foto_jpeg_girada(tmp_path / "otra.jpg")
    responder(monkeypatch, question=QMessageBox.StandardButton.Save,
              getSaveFileName=(str(tmp_path / "guardado.grabado"), proyecto.FILTRO),
              getOpenFileName=(str(otra_foto), ""))
    v._abrir()
    assert proyecto.abrir(tmp_path / "guardado.grabado").ajustes.nitidez == 50
    assert v.documento.ruta == otra_foto and not v.documento.modificado

    # Descartar al cerrar: se cierra sin guardar.
    v.documento.cambiar_ajustes(nitidez=10)
    responder(monkeypatch, question=QMessageBox.StandardButton.Discard)
    v.close()
    assert not v.isVisible()
    assert proyecto.abrir(tmp_path / "guardado.grabado").ajustes.nitidez == 50


def test_abrir_un_archivo_danado_avisa(app, ventanas, tmp_path, monkeypatch):
    v = ventanas()
    ruta = tmp_path / "malo.grabado"
    ruta.write_bytes(b"basura")
    avisos = []
    responder(monkeypatch, getOpenFileName=(str(ruta), proyecto.FILTRO))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: avisos.append(a[1]))
    v.accion_abrir_proyecto.trigger()
    assert avisos == ["No se pudo abrir el proyecto"]
    assert not v.documento.tiene_foto
