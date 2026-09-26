"""Tramado: convierte cada capa tonal en un patrón de puntos con degradado."""

import numpy as np
from numba import njit

from grabado.tonal import CAPAS_GRABADAS, Capa, Cortes

# Densidad de puntos en el lado claro de cada capa; en el lado oscuro es 1.
DENSIDAD_MINIMA = 0.3

# Núcleos de difusión de error: (dy, dx, peso). dx se invierte en las filas de ida y vuelta.
NUCLEOS = {
    "jarvis": [
        (0, 1, 7), (0, 2, 5),
        (1, -2, 3), (1, -1, 5), (1, 0, 7), (1, 1, 5), (1, 2, 3),
        (2, -2, 1), (2, -1, 3), (2, 0, 5), (2, 1, 3), (2, 2, 1),
    ],
}

METODO_POR_DEFECTO = "jarvis"


def densidad(gris: np.ndarray, cortes: Cortes, etiquetas: np.ndarray) -> np.ndarray:
    """Fracción de puntos a grabar en cada píxel: 1 en el lado oscuro de su capa, DENSIDAD_MINIMA en el claro."""
    limites = (0.0, *cortes, 255.0)
    resultado = np.zeros(gris.shape, np.float32)
    for capa in CAPAS_GRABADAS:
        bajo, alto = limites[capa], limites[capa + 1]
        en_capa = etiquetas == capa
        t = np.clip((gris[en_capa] - bajo) / max(alto - bajo, 1e-6), 0.0, 1.0)
        resultado[en_capa] = 1.0 - t * (1.0 - DENSIDAD_MINIMA)
    return resultado


def tramar(
    densidades: np.ndarray, etiquetas: np.ndarray, metodo: str = METODO_POR_DEFECTO
) -> dict[Capa, np.ndarray]:
    """Devuelve, por cada capa grabada, una matriz booleana: True = grabar ese punto."""
    nucleo = np.array(NUCLEOS[metodo], np.float64)
    dys = nucleo[:, 0].astype(np.int64)
    dxs = nucleo[:, 1].astype(np.int64)
    pesos = nucleo[:, 2]
    trabajo = densidades.astype(np.float64)
    return {
        capa: _difundir(trabajo, etiquetas, np.uint8(capa), dys, dxs, pesos)
        for capa in CAPAS_GRABADAS
    }


@njit(cache=True, nogil=True)
def _difundir(densidades, etiquetas, capa, dys, dxs, pesos):
    # El error solo se reparte entre píxeles de la misma capa, para que no aparezcan
    # puntos fuera de ella; los pesos se renormalizan con los vecinos válidos.
    alto, ancho = densidades.shape
    valores = densidades.copy()
    salida = np.zeros((alto, ancho), np.bool_)
    for y in range(alto):
        sentido = 1 if y % 2 == 0 else -1
        for i in range(ancho):
            x = i if sentido == 1 else ancho - 1 - i
            if etiquetas[y, x] != capa:
                continue
            v = valores[y, x]
            punto = 1.0 if v >= 0.5 else 0.0
            salida[y, x] = punto > 0.0
            error = v - punto
            total = 0.0
            for k in range(pesos.shape[0]):
                yy = y + dys[k]
                xx = x + dxs[k] * sentido
                if yy < alto and 0 <= xx < ancho and etiquetas[yy, xx] == capa:
                    total += pesos[k]
            if total == 0.0:
                continue
            for k in range(pesos.shape[0]):
                yy = y + dys[k]
                xx = x + dxs[k] * sentido
                if yy < alto and 0 <= xx < ancho and etiquetas[yy, xx] == capa:
                    valores[yy, xx] += error * pesos[k] / total
    return salida
