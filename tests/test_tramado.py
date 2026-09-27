import numpy as np
import pytest

from grabado.tonal import CAPAS_GRABADAS, Capa, separar
from grabado.tramado import (
    DENSIDAD_MINIMA,
    METODO_POR_DEFECTO,
    METODOS,
    PASO_SEMITONO,
    densidad,
    tramar,
)

TODOS = list(METODOS)


def test_densidad_va_de_uno_a_la_minima_dentro_de_la_capa():
    gris = np.array([[0.0, 30.0, 59.9, 60.0, 90.0]], np.float32)
    cortes = (60.0, 120.0, 180.0)
    d = densidad(gris, cortes, separar(gris, cortes))
    assert d[0, 0] == pytest.approx(1.0)
    assert d[0, 1] == pytest.approx(1.0 - 0.5 * (1.0 - DENSIDAD_MINIMA))
    assert d[0, 2] == pytest.approx(DENSIDAD_MINIMA, abs=0.01)
    # Al pasar a la capa siguiente se vuelve a empezar desde 1.
    assert d[0, 3] == pytest.approx(1.0)


def test_se_ofrecen_los_cuatro_metodos_con_jarvis_por_defecto():
    nombres = [m.nombre for m in METODOS.values()]
    assert nombres == ["Jarvis", "Floyd-Steinberg", "Stucki", "Semitono"]
    assert METODO_POR_DEFECTO == "jarvis"


@pytest.mark.parametrize("metodo", TODOS)
def test_claro_y_fondo_no_se_graban(metodo):
    gris = np.full((20, 20), 250.0, np.float32)
    etiquetas = separar(gris, (60.0, 120.0, 180.0))
    capas = tramar(densidad(gris, (60.0, 120.0, 180.0), etiquetas), etiquetas, metodo)
    assert not any(capas[c].any() for c in CAPAS_GRABADAS)


@pytest.mark.parametrize("metodo", TODOS)
@pytest.mark.parametrize("valor", [DENSIDAD_MINIMA, 0.4, 0.7])
def test_densidad_uniforme_se_respeta(metodo, valor):
    etiquetas = np.full((96, 96), Capa.OSCURO, np.uint8)
    densidades = np.full((96, 96), valor, np.float32)
    puntos = tramar(densidades, etiquetas, metodo)[Capa.OSCURO]
    assert puntos.mean() == pytest.approx(valor, abs=0.02)


@pytest.mark.parametrize("metodo", TODOS)
def test_densidad_uno_graba_toda_la_capa(metodo):
    etiquetas = np.full((40, 40), Capa.NEGRO, np.uint8)
    puntos = tramar(np.ones((40, 40), np.float32), etiquetas, metodo)[Capa.NEGRO]
    assert puntos.all()


@pytest.mark.parametrize("metodo", TODOS)
def test_degradado_dentro_de_una_capa(metodo):
    etiquetas = np.full((120, 120), Capa.MEDIO, np.uint8)
    densidades = np.tile(np.linspace(1.0, DENSIDAD_MINIMA, 120, dtype=np.float32), (120, 1))
    puntos = tramar(densidades, etiquetas, metodo)[Capa.MEDIO]
    columnas = puntos.mean(axis=0)
    lado_oscuro = columnas[:20].mean()
    lado_claro = columnas[-20:].mean()
    assert lado_oscuro > 0.9
    assert lado_claro == pytest.approx(DENSIDAD_MINIMA + 0.03, abs=0.06)
    # La densidad baja de forma gradual, no en un salto.
    tercios = [columnas[i : i + 40].mean() for i in (0, 40, 80)]
    assert tercios[0] > tercios[1] > tercios[2]


@pytest.mark.parametrize("metodo", TODOS)
def test_puntos_solo_dentro_de_su_capa(metodo):
    rng = np.random.default_rng(0)
    etiquetas = rng.integers(0, 4, (60, 60)).astype(np.uint8)
    densidades = np.full((60, 60), 0.7, np.float32)
    capas = tramar(densidades, etiquetas, metodo)
    for capa in CAPAS_GRABADAS:
        assert not capas[capa][etiquetas != capa].any()


def test_semitono_es_una_cuadricula_regular():
    etiquetas = np.full((64, 64), Capa.OSCURO, np.uint8)
    puntos = tramar(np.full((64, 64), 0.4, np.float32), etiquetas, "semitono")[Capa.OSCURO]
    # Cuadrícula girada 45°: se repite al moverse un paso en ambas direcciones.
    assert (puntos == np.roll(puntos, (PASO_SEMITONO, PASO_SEMITONO), axis=(0, 1))).all()
    assert (puntos == np.roll(puntos, 2 * PASO_SEMITONO, axis=1)).all()


@pytest.mark.parametrize("valor", [DENSIDAD_MINIMA, 0.4, 0.5])
def test_semitono_agrupa_los_puntos_sin_pixeles_sueltos(valor):
    etiquetas = np.full((64, 64), Capa.MEDIO, np.uint8)
    puntos = tramar(np.full((64, 64), valor, np.float32), etiquetas, "semitono")[Capa.MEDIO]
    vecinos = (
        np.roll(puntos, 1, 0) | np.roll(puntos, -1, 0) | np.roll(puntos, 1, 1) | np.roll(puntos, -1, 1)
    )
    assert not (puntos & ~vecinos).any()
