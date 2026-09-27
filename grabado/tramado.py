"""Tramado: convierte cada capa tonal en un patrón de puntos con degradado."""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numba import njit

from grabado.tonal import CAPAS_GRABADAS, Capa, Cortes

METODO_POR_DEFECTO = "jarvis"

# Densidad de puntos en el lado claro de cada capa; en el lado oscuro es 1.
DENSIDAD_MINIMA = 0.3

# Núcleos de difusión de error: (dy, dx, peso). dx se invierte en las filas de ida y vuelta.
NUCLEOS = {
    "jarvis": [
        (0, 1, 7), (0, 2, 5),
        (1, -2, 3), (1, -1, 5), (1, 0, 7), (1, 1, 5), (1, 2, 3),
        (2, -2, 1), (2, -1, 3), (2, 0, 5), (2, 1, 3), (2, 2, 1),
    ],
    "floyd_steinberg": [
        (0, 1, 7),
        (1, -1, 3), (1, 0, 5), (1, 1, 1),
    ],
    "stucki": [
        (0, 1, 8), (0, 2, 4),
        (1, -2, 2), (1, -1, 4), (1, 0, 8), (1, 1, 4), (1, 2, 2),
        (2, -2, 1), (2, -1, 2), (2, 0, 4), (2, 1, 2), (2, 2, 1),
    ],
}

# Semitono: puntos agrupados sobre una cuadrícula girada 45°, a PASO_SEMITONO píxeles
# en diagonal. A 254 DPI (0,1 mm por píxel) queda un punto cada 0,57 mm (~45 líneas por
# pulgada) con 32 píxeles por celda, es decir 33 niveles de densidad. Con la densidad
# mínima de 0,3 cada punto ocupa ~10 píxeles (~0,3 mm): mucho más grande que el haz, así
# que la madera lo marca aunque queme o absorba de forma irregular, cosa que no pasa con
# los píxeles sueltos de la difusión de error. Una celda más grande daría más niveles
# pero una trama visible a la distancia de mirada; una más chica, puntos que se funden.
PASO_SEMITONO = 4


@dataclass(frozen=True)
class MetodoTramado:
    # Nombre que ve el usuario.
    nombre: str
    # (densidades, etiquetas, capa) -> matriz booleana con los puntos de esa capa.
    tramar_capa: Callable[[np.ndarray, np.ndarray, int], np.ndarray]


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
    tramar_capa = METODOS[metodo].tramar_capa
    trabajo = densidades.astype(np.float64)
    return {capa: tramar_capa(trabajo, etiquetas, capa) for capa in CAPAS_GRABADAS}


def _difusion(nucleo: list[tuple[int, int, int]]) -> Callable[[np.ndarray, np.ndarray, int], np.ndarray]:
    matriz = np.array(nucleo, np.float64)
    dys = matriz[:, 0].astype(np.int64)
    dxs = matriz[:, 1].astype(np.int64)
    pesos = matriz[:, 2]

    def tramar_capa(densidades, etiquetas, capa):
        return _difundir(densidades, etiquetas, np.uint8(capa), dys, dxs, pesos)

    return tramar_capa


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


def _umbrales_semitono(paso: int) -> np.ndarray:
    """Matriz de umbrales de 2·paso × 2·paso con dos celdas de punto agrupado a 45°.

    El punto crece desde el centro de cada celda: se ordenan los píxeles por la función
    de punto cos(u) + cos(v) en coordenadas giradas y el orden da el umbral, de modo que
    una densidad d enciende la fracción d de cada celda.
    """
    lado = 2 * paso
    y, x = np.mgrid[0:lado, 0:lado].astype(np.float64)
    u = np.pi * (x + y) / paso
    v = np.pi * (x - y) / paso
    punto = np.cos(u) + np.cos(v)
    # Desempate leve para que el punto crezca redondo y no en orden de barrido.
    distancia = np.minimum.reduce([
        np.hypot(x - cx, y - cy)
        for cx, cy in [(0, 0), (lado, 0), (0, lado), (lado, lado), (paso, paso)]
    ])
    orden = np.lexsort((distancia.ravel(), -np.round(punto.ravel(), 9)))
    rango = np.empty(lado * lado, np.float64)
    rango[orden] = np.arange(lado * lado)
    return ((rango + 0.5) / (lado * lado)).reshape(lado, lado)


_UMBRALES_SEMITONO = _umbrales_semitono(PASO_SEMITONO)


def _semitono(densidades: np.ndarray, etiquetas: np.ndarray, capa: int) -> np.ndarray:
    alto, ancho = densidades.shape
    lado = _UMBRALES_SEMITONO.shape[0]
    repeticiones = (-(-alto // lado), -(-ancho // lado))
    umbrales = np.tile(_UMBRALES_SEMITONO, repeticiones)[:alto, :ancho]
    return (densidades > umbrales) & (etiquetas == capa)


# Métodos de tramado disponibles, en el orden en que se ofrecen al usuario.
METODOS: dict[str, MetodoTramado] = {
    "jarvis": MetodoTramado("Jarvis", _difusion(NUCLEOS["jarvis"])),
    "floyd_steinberg": MetodoTramado("Floyd-Steinberg", _difusion(NUCLEOS["floyd_steinberg"])),
    "stucki": MetodoTramado("Stucki", _difusion(NUCLEOS["stucki"])),
    "semitono": MetodoTramado("Semitono", _semitono),
}
