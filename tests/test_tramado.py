import numpy as np
import pytest

from grabado.tonal import CAPAS_GRABADAS, Capa, separar
from grabado.tramado import DENSIDAD_MINIMA, NUCLEOS, densidad, tramar


def test_densidad_va_de_uno_a_la_minima_dentro_de_la_capa():
    gris = np.array([[0.0, 30.0, 59.9, 60.0, 90.0]], np.float32)
    cortes = (60.0, 120.0, 180.0)
    d = densidad(gris, cortes, separar(gris, cortes))
    assert d[0, 0] == pytest.approx(1.0)
    assert d[0, 1] == pytest.approx(1.0 - 0.5 * (1.0 - DENSIDAD_MINIMA))
    assert d[0, 2] == pytest.approx(DENSIDAD_MINIMA, abs=0.01)
    # Al pasar a la capa siguiente se vuelve a empezar desde 1.
    assert d[0, 3] == pytest.approx(1.0)


def test_claro_y_fondo_no_se_graban():
    gris = np.full((20, 20), 250.0, np.float32)
    etiquetas = separar(gris, (60.0, 120.0, 180.0))
    capas = tramar(densidad(gris, (60.0, 120.0, 180.0), etiquetas), etiquetas)
    assert not any(capas[c].any() for c in CAPAS_GRABADAS)


@pytest.mark.parametrize("metodo", list(NUCLEOS))
def test_densidad_uniforme_se_respeta(metodo):
    etiquetas = np.full((100, 100), Capa.OSCURO, np.uint8)
    densidades = np.full((100, 100), 0.4, np.float32)
    puntos = tramar(densidades, etiquetas, metodo)[Capa.OSCURO]
    assert puntos.mean() == pytest.approx(0.4, abs=0.02)


@pytest.mark.parametrize("metodo", list(NUCLEOS))
def test_degradado_dentro_de_una_capa(metodo):
    etiquetas = np.full((120, 120), Capa.MEDIO, np.uint8)
    densidades = np.tile(np.linspace(1.0, DENSIDAD_MINIMA, 120, dtype=np.float32), (120, 1))
    puntos = tramar(densidades, etiquetas, metodo)[Capa.MEDIO]
    lado_oscuro = puntos[:, :20].mean()
    lado_claro = puntos[:, -20:].mean()
    assert lado_oscuro > 0.9
    assert lado_claro == pytest.approx(DENSIDAD_MINIMA + 0.03, abs=0.06)


def test_puntos_solo_dentro_de_su_capa():
    rng = np.random.default_rng(0)
    etiquetas = rng.integers(0, 4, (60, 60)).astype(np.uint8)
    densidades = np.full((60, 60), 0.7, np.float32)
    capas = tramar(densidades, etiquetas)
    for capa in CAPAS_GRABADAS:
        assert not capas[capa][etiquetas != capa].any()
