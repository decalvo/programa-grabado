import numpy as np
import pytest
from PIL import Image

from grabado import calibracion
from grabado.proceso import MM_POR_PULGADA
from grabado.tramado import DENSIDAD_MINIMA

DPI = 127


@pytest.fixture(scope="module")
def plantilla():
    return calibracion.crear(DPI)


def interior(plantilla, i):
    x, y = plantilla.posiciones[i]
    lado = plantilla.lado_px
    return plantilla.capas[i][y : y + lado, x : x + lado]


def test_cuadro_mide_15_mm_a_los_dpi(plantilla):
    assert plantilla.lado_px == round(15 / MM_POR_PULGADA * DPI)
    assert calibracion.crear(254).lado_px == 150


def test_ocho_cuadros_en_posiciones_distintas(plantilla):
    assert len(plantilla.capas) == 8
    assert len(set(plantilla.posiciones)) == 8
    alto, ancho = plantilla.capas[0].shape
    lado = plantilla.lado_px
    for x, y in plantilla.posiciones:
        assert 0 <= x and x + lado <= ancho
        assert 0 <= y and y + lado <= alto


def test_cada_cuadro_solo_esta_en_su_capa(plantilla):
    lado = plantilla.lado_px
    for i, (x, y) in enumerate(plantilla.posiciones):
        for j, capa in enumerate(plantilla.capas):
            zona = capa[y : y + lado, x : x + lado]
            if i == j:
                assert zona.any()
            else:
                assert not zona.any()


def test_las_capas_no_se_superponen(plantilla):
    suma = np.sum(plantilla.capas, axis=0)
    assert suma.max() == 1


def test_numero_grabado_al_lado_de_su_cuadro(plantilla):
    lado = plantilla.lado_px
    for i, (x, y) in enumerate(plantilla.posiciones):
        capa = plantilla.capas[i].copy()
        capa[y : y + lado, x : x + lado] = False
        filas, columnas = np.nonzero(capa)
        assert filas.size > 0, f"falta el número del cuadro {i + 1}"
        # A la izquierda del cuadro y dentro de su altura.
        assert columnas.max() < x
        assert filas.min() >= y and filas.max() < y + lado
        alto_mm = (filas.max() - filas.min() + 1) / DPI * MM_POR_PULGADA
        assert 4 <= alto_mm <= 6


def test_los_numeros_son_distintos(plantilla):
    lado = plantilla.lado_px
    formas = set()
    for i, (x, y) in enumerate(plantilla.posiciones):
        capa = plantilla.capas[i].copy()
        capa[y : y + lado, x : x + lado] = False
        filas, columnas = np.nonzero(capa)
        forma = capa[filas.min() : filas.max() + 1, columnas.min() : columnas.max() + 1]
        formas.add((forma.shape, forma.tobytes()))
    assert len(formas) == 8


def test_degradado_de_densidad_dentro_del_cuadro(plantilla):
    cuadro = interior(plantilla, 0)
    tercio = cuadro.shape[1] // 3
    denso = cuadro[:, :tercio].mean()
    claro = cuadro[:, -tercio:].mean()
    assert denso > 0.85
    assert claro == pytest.approx(DENSIDAD_MINIMA + (1 - DENSIDAD_MINIMA) / 6, abs=0.1)
    assert denso > claro + 0.3


def test_exporta_ocho_bmp_alineados_y_la_tabla(plantilla, tmp_path):
    archivos = calibracion.exportar(plantilla, tmp_path)
    bmps = [a for a in archivos if a.suffix == ".bmp"]
    assert [a.name for a in bmps] == [f"calibracion_{n}.bmp" for n in range(1, 9)]
    tamanos = set()
    for ruta, capa in zip(bmps, plantilla.capas):
        with Image.open(ruta) as imagen:
            assert imagen.mode == "1"
            assert round(imagen.info["dpi"][0]) == DPI
            tamanos.add(imagen.size)
            assert ((np.asarray(imagen.convert("L")) == 0) == capa).all()
    assert tamanos == {plantilla.capas[0].shape[::-1]}

    texto = (tmp_path / "calibracion_potencias.txt").read_text(encoding="utf-8")
    assert "Cuadro 1: 10 %" in texto
    assert "Cuadro 8: 80 %" in texto
    assert f"{MM_POR_PULGADA / DPI:.4f} mm" in texto


def test_usa_el_metodo_de_tramado(monkeypatch):
    usados = []
    original = calibracion.tramado.tramar

    def espia(densidades, etiquetas, metodo):
        usados.append(metodo)
        return original(densidades, etiquetas, "jarvis")

    monkeypatch.setattr(calibracion.tramado, "tramar", espia)
    calibracion.crear(50, "otro")
    assert usados and set(usados) == {"otro"}
