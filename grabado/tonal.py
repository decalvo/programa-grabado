"""Separación tonal: reparte los píxeles del sujeto en capas tonales."""

from enum import IntEnum

import numpy as np


class Capa(IntEnum):
    NEGRO = 0
    OSCURO = 1
    MEDIO = 2
    CLARO = 3


# Claro no se graba: queda como madera natural.
CAPAS_GRABADAS = (Capa.NEGRO, Capa.OSCURO, Capa.MEDIO)

# Etiqueta de los píxeles que no son sujeto.
FONDO = 255

Cortes = tuple[float, float, float]

CORTES_POR_DEFECTO: Cortes = (64.0, 128.0, 192.0)


def cortes_automaticos(gris: np.ndarray, mascara: np.ndarray | None = None) -> Cortes:
    """Coloca los 3 cortes tonales para que cada capa reciba una parte parecida del sujeto."""
    valores = gris[mascara] if mascara is not None else gris.ravel()
    if valores.size == 0:
        return CORTES_POR_DEFECTO
    c1, c2, c3 = np.percentile(valores, [25, 50, 75])
    return float(c1), float(c2), float(c3)


def separar(gris: np.ndarray, cortes: Cortes, mascara: np.ndarray | None = None) -> np.ndarray:
    """Etiqueta cada píxel con su capa tonal (o FONDO). Cada píxel pertenece a una sola capa."""
    etiquetas = np.digitize(gris, cortes).astype(np.uint8)
    if mascara is not None:
        etiquetas[~mascara] = FONDO
    return etiquetas


def mover_corte(cortes: Cortes, indice: int, valor: float) -> Cortes:
    """Mueve un corte tonal sin cruzar a sus vecinos: queda al menos 1 tono de cada lado.

    Si los cortes de partida están pegados (p. ej. dos iguales), primero se separan.
    """
    c = list(ordenar_cortes(cortes))
    bajo = c[indice - 1] + 1 if indice > 0 else 0.0
    alto = c[indice + 1] - 1 if indice < 2 else 255.0
    c[indice] = min(max(float(valor), bajo), alto)
    return c[0], c[1], c[2]


def ordenar_cortes(cortes: Cortes) -> Cortes:
    """Deja los cortes dentro de 0-255 y estrictamente crecientes, a 1 tono como mínimo."""
    c0, c1, c2 = (min(max(float(v), 0.0), 255.0) for v in cortes)
    c1 = max(c1, c0 + 1)
    c2 = min(max(c2, c1 + 1), 255.0)
    c1 = min(c1, c2 - 1)
    c0 = min(max(c0, 0.0), c1 - 1)
    return c0, c1, c2
