"""Ajustes previos: brillo, contraste y nitidez del sujeto antes de la separación tonal.

Todos los valores van de un mínimo a un máximo con 0 como neutro, para que el panel los
muestre como deslizadores enteros y `Ajustes` los guarde tal cual.
"""

import numpy as np
from PIL import Image

MM_POR_PULGADA = 25.4

# Brillo: tonos (de 0 a 255) que se suman a cada píxel.
BRILLO_MIN, BRILLO_MAX = -100, 100

# Contraste: multiplica la distancia de cada tono al gris medio por 4 ** (contraste / 100),
# es decir de ×0,25 (-100) a ×4 (+100). La escala es logarítmica para que +50 y -50 sean
# cambios de la misma magnitud (×2 y ×0,5) y el máximo alcance a estirar una foto muy plana.
CONTRASTE_MIN, CONTRASTE_MAX = -100, 100
GRIS_MEDIO = 128.0

# Nitidez: fuerza de la máscara de enfoque en % (100 = suma una vez el detalle fino).
NITIDEZ_MIN, NITIDEZ_MAX = 0, 200

# Radio del detalle que realza la nitidez, en mm sobre la madera. Se mide en mm y no en
# píxeles de la foto para que el realce sea el mismo con cualquier foto y en la vista previa
# (que se calcula a menos DPI). 0,25 mm es del orden de un punto del tramado (0,1-0,6 mm):
# realza ojos, pelo y bordes sin inventar textura más fina de lo que la madera puede marcar.
RADIO_NITIDEZ_MM = 0.25

# Auto-mejorar estira los tonos del sujeto entre estos percentiles hasta estos tonos, así
# un 1 % de píxeles sueltos (brillos, sombras duras) no frena el estiramiento.
PERCENTILES_AUTO = (1.0, 99.0)
TONOS_AUTO = (8.0, 247.0)
NITIDEZ_AUTO = 50

# Lado mayor de la foto con que se calculan las estadísticas de auto-mejorar.
LADO_AUTO = 800


def factor_contraste(contraste: float) -> float:
    return 4.0 ** (contraste / 100.0)


def aplicar(
    gris: np.ndarray,
    brillo: float = 0,
    contraste: float = 0,
    nitidez: float = 0,
    dpi: float = 254,
    mascara: np.ndarray | None = None,
) -> np.ndarray:
    """Devuelve `gris` (0-255) con brillo, contraste y nitidez aplicados; con todo en 0 lo devuelve igual.

    `dpi` es la resolución de `gris` sobre la madera, para medir el radio de la nitidez en mm.
    Con `mascara` (True = sujeto) la nitidez solo mira el sujeto: el fondo no deja halos en el
    borde. El fondo no se graba, así que lo que le pase no importa.
    """
    resultado = np.asarray(gris, np.float32)
    if brillo or contraste:
        f = factor_contraste(contraste)
        resultado = np.clip((resultado - GRIS_MEDIO) * f + GRIS_MEDIO + brillo, 0.0, 255.0)
    if nitidez:
        sigma = RADIO_NITIDEZ_MM / MM_POR_PULGADA * dpi
        suave = _desenfocar(resultado, sigma, mascara)
        resultado = np.clip(resultado + (nitidez / 100.0) * (resultado - suave), 0.0, 255.0)
    return resultado.astype(np.float32, copy=False)


def auto_mejorar(gris: np.ndarray, mascara: np.ndarray | None = None) -> dict[str, int]:
    """Brillo, contraste y nitidez que estiran los tonos del sujeto a casi toda la gama.

    Solo cuentan los píxeles del sujeto. No baja el contraste de una foto que ya lo tiene.
    Devuelve los valores enteros de los deslizadores, listos para `Ajustes`.
    """
    valores = np.asarray(gris, np.float32)
    valores = valores[mascara] if mascara is not None else valores.ravel()
    if valores.size == 0:
        return {"brillo": 0, "contraste": 0, "nitidez": 0}
    bajo, alto = np.percentile(valores, PERCENTILES_AUTO)
    destino_bajo, destino_alto = TONOS_AUTO
    f = (destino_alto - destino_bajo) / max(float(alto - bajo), 1e-6)
    f = min(max(f, 1.0), factor_contraste(CONTRASTE_MAX))
    contraste = round(100.0 * np.log(f) / np.log(4.0))
    # El brillo se calcula con el contraste ya redondeado: así se aplica lo que muestra el deslizador.
    f = factor_contraste(contraste)
    centro = (bajo + alto) / 2.0
    brillo = round((destino_bajo + destino_alto) / 2.0 - GRIS_MEDIO - (centro - GRIS_MEDIO) * f)
    brillo = min(max(brillo, BRILLO_MIN), BRILLO_MAX)
    return {"brillo": int(brillo), "contraste": int(contraste), "nitidez": NITIDEZ_AUTO}


def auto_mejorar_foto(foto: Image.Image, mascara: Image.Image | None = None) -> dict[str, int]:
    """`auto_mejorar` sobre la foto de origen (blanco en `mascara` = sujeto), reducida para ir rápido."""
    if mascara is None and "A" in foto.getbands():
        mascara = foto.getchannel("A")
    gris = foto.convert("RGB").convert("L")
    escala = min(1.0, LADO_AUTO / max(gris.size))
    tamano = (max(1, round(gris.width * escala)), max(1, round(gris.height * escala)))
    gris = gris.resize(tamano, Image.Resampling.BILINEAR)
    sujeto = None
    if mascara is not None:
        sujeto = np.asarray(mascara.convert("L").resize(tamano, Image.Resampling.BILINEAR)) >= 128
    return auto_mejorar(np.asarray(gris), sujeto)


def _desenfocar(gris: np.ndarray, sigma: float, mascara: np.ndarray | None) -> np.ndarray:
    """Desenfoque gaussiano; con máscara, promedia solo píxeles del sujeto."""
    if mascara is None:
        return _gauss(gris, sigma)
    peso = mascara.astype(np.float32)
    suma = _gauss(gris * peso, sigma)
    cantidad = _gauss(peso, sigma)
    return np.where(cantidad > 1e-3, suma / np.maximum(cantidad, 1e-3), gris)


def _gauss(imagen: np.ndarray, sigma: float) -> np.ndarray:
    """Desenfoque gaussiano separable con los bordes extendidos."""
    radio = max(1, int(np.ceil(3 * sigma)))
    x = np.arange(-radio, radio + 1, dtype=np.float32)
    nucleo = np.exp(-0.5 * (x / max(sigma, 1e-3)) ** 2)
    nucleo /= nucleo.sum()
    resultado = imagen.astype(np.float32)
    for eje in (0, 1):
        relleno = [(0, 0), (0, 0)]
        relleno[eje] = (radio, radio)
        ampliada = np.pad(resultado, relleno, mode="edge")
        n = resultado.shape[eje]
        acumulado = np.zeros_like(resultado)
        for i, peso in enumerate(nucleo):
            tramo = ampliada[i : i + n, :] if eje == 0 else ampliada[:, i : i + n]
            acumulado += peso * tramo
        resultado = acumulado
    return resultado
