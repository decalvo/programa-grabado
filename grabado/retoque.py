"""Retoque del recorte: trazos de pincel que borran o recuperan zonas de la máscara del sujeto.

Sin Qt: la ventana traduce el ratón a puntos de la foto y usa estas funciones.
La máscara es una imagen "L" del tamaño de la foto: blanco = sujeto, negro = fondo.
"""

from dataclasses import dataclass

from PIL import Image, ImageDraw

BORRAR = "borrar"  # Lo pintado pasa a ser fondo.
RECUPERAR = "recuperar"  # Lo pintado vuelve a ser sujeto.

SUJETO = 255
FONDO = 0

# Trazos que se pueden deshacer.
LIMITE_DESHACER = 20

Punto = tuple[float, float]
Caja = tuple[int, int, int, int]  # izquierda, arriba, derecha, abajo (derecha y abajo excluidas)


def ubicar_imagen(tamano_imagen: tuple[int, int], tamano_widget: tuple[int, int]) -> tuple[int, int, int, int]:
    """Dónde queda la imagen ajustada al widget sin deformarla y centrada: x, y, ancho, alto.

    Calcula lo mismo que `QPixmap.scaled(..., KeepAspectRatio)` con alineación al centro.
    """
    ancho, alto = tamano_imagen
    ancho_w, alto_w = tamano_widget
    if ancho <= 0 or alto <= 0 or ancho_w <= 0 or alto_w <= 0:
        return 0, 0, 0, 0
    ancho_ajustado = alto_w * ancho // alto
    if ancho_ajustado <= ancho_w:
        ancho_final, alto_final = ancho_ajustado, alto_w
    else:
        ancho_final, alto_final = ancho_w, ancho_w * alto // ancho
    return (ancho_w - ancho_final) // 2, (alto_w - alto_final) // 2, ancho_final, alto_final


def escala_en_pantalla(tamano_imagen: tuple[int, int], tamano_widget: tuple[int, int]) -> float:
    """Píxeles de pantalla por píxel de la foto."""
    _, _, ancho, _ = ubicar_imagen(tamano_imagen, tamano_widget)
    return ancho / tamano_imagen[0] if tamano_imagen[0] else 0.0


def widget_a_imagen(punto: Punto, tamano_imagen: tuple[int, int], tamano_widget: tuple[int, int]) -> Punto:
    """Convierte un punto del widget a coordenadas de la foto (el píxel i ocupa de i a i + 1)."""
    x, y, ancho, alto = ubicar_imagen(tamano_imagen, tamano_widget)
    if ancho == 0 or alto == 0:
        return 0.0, 0.0
    return (punto[0] - x) * tamano_imagen[0] / ancho, (punto[1] - y) * tamano_imagen[1] / alto


def caja_del_trazo(puntos: list[Punto], radio: float, tamano: tuple[int, int]) -> Caja | None:
    """Rectángulo de la foto que un trazo puede tocar, o None si queda fuera."""
    margen = radio + 1
    izquierda = max(0, int(min(p[0] for p in puntos) - margen))
    arriba = max(0, int(min(p[1] for p in puntos) - margen))
    derecha = min(tamano[0], int(max(p[0] for p in puntos) + margen) + 1)
    abajo = min(tamano[1], int(max(p[1] for p in puntos) + margen) + 1)
    if izquierda >= derecha or arriba >= abajo:
        return None
    return izquierda, arriba, derecha, abajo


def aplicar_trazo(mascara: Image.Image, puntos: list[Punto], radio: float, modo: str) -> Caja | None:
    """Pinta un trazo de pincel redondo sobre la máscara (se modifica en el lugar).

    `puntos` en coordenadas de la foto; `radio` en píxeles de la foto. Devuelve la zona
    que pudo cambiar, o None si el trazo quedó fuera de la foto.
    """
    if modo not in (BORRAR, RECUPERAR):
        raise ValueError(f"Modo de retoque desconocido: {modo}")
    if not puntos:
        return None
    radio = max(radio, 0.75)  # Al menos un píxel, aunque el pincel sea diminuto.
    caja = caja_del_trazo(puntos, radio, mascara.size)
    if caja is None:
        return None
    color = FONDO if modo == BORRAR else SUJETO
    dibujo = ImageDraw.Draw(mascara)
    # En PIL la coordenada entera es el centro del píxel.
    centros = [(x - 0.5, y - 0.5) for x, y in puntos]
    for x, y in centros:
        dibujo.ellipse((x - radio, y - radio, x + radio, y + radio), fill=color)
    if len(centros) > 1:
        dibujo.line(centros, fill=color, width=max(1, round(2 * radio)), joint="curve")
    return caja


def mascara_inicial(foto: Image.Image) -> Image.Image:
    """La máscara de partida cuando aún no se eliminó el fondo: toda la foto es sujeto
    (o lo que diga la transparencia de la foto, igual que al procesar)."""
    if "A" in foto.getbands():
        return foto.getchannel("A").point([0] * 128 + [255] * 128)
    return Image.new("L", foto.size, SUJETO)


@dataclass
class _Paso:
    caja: Caja
    parche: Image.Image  # la zona de la máscara antes del trazo
    sin_mascara: bool  # antes del trazo la foto no tenía máscara


class Retoque:
    """Aplica trazos a la máscara del recorte y recuerda cómo deshacerlos.

    Cada trazo produce una máscara nueva (la anterior no se toca). Solo se guarda la zona
    que cambió, para que deshacer no ocupe una foto entera por trazo. Si la máscara del
    documento cambia por otro motivo (otra foto, eliminar fondo de nuevo), lo guardado deja
    de valer y se descarta.
    """

    def __init__(self, limite: int = LIMITE_DESHACER) -> None:
        self._limite = limite
        self._pasos: list[_Paso] = []
        self._ultima: Image.Image | None = None  # la máscara que dejó el último trazo o deshacer

    def trazar(
        self,
        foto: Image.Image,
        mascara: Image.Image | None,
        puntos: list[Punto],
        radio: float,
        modo: str,
    ) -> Image.Image | None:
        """Devuelve la máscara con el trazo aplicado, o None si el trazo quedó fuera de la foto."""
        if mascara is not self._ultima:
            self._pasos.clear()
        sin_mascara = mascara is None
        nueva = mascara_inicial(foto) if sin_mascara else mascara.convert("L").copy()
        caja = caja_del_trazo(puntos, max(radio, 0.75), nueva.size) if puntos else None
        if caja is None:
            return None
        parche = nueva.crop(caja)
        aplicar_trazo(nueva, puntos, radio, modo)
        self._pasos.append(_Paso(caja, parche, sin_mascara))
        del self._pasos[: -self._limite]
        self._ultima = nueva
        return nueva

    def puede_deshacer(self, mascara: Image.Image | None) -> bool:
        return bool(self._pasos) and mascara is self._ultima

    def deshacer(self, mascara: Image.Image | None) -> Image.Image | None:
        """La máscara de antes del último trazo (None si antes no había máscara)."""
        if not self.puede_deshacer(mascara):
            raise RuntimeError("No hay trazo que deshacer")
        paso = self._pasos.pop()
        if paso.sin_mascara:
            anterior = None
        else:
            anterior = mascara.copy()
            anterior.paste(paso.parche, paso.caja[:2])
        self._ultima = anterior
        return anterior
