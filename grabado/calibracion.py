"""Plantilla de calibración: 8 cuadros tramados, uno por BMP, para probar 8 potencias en una madera."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from grabado import tramado
from grabado.exportar import a_bmp
from grabado.proceso import MM_POR_PULGADA
from grabado.tonal import Capa

CUADROS = 8
COLUMNAS = 4
LADO_MM = 15.0
ALTO_NUMERO_MM = 5.0
# Espacio a la izquierda de cada cuadro para su número (incluye la separación con el cuadro).
ZONA_NUMERO_MM = 7.0
SEPARACION_NUMERO_MM = 1.5
MARGEN_MM = 5.0
SEPARACION_MM = 5.0
# Potencia sugerida (%) para el cuadro 1, 2, … 8.
POTENCIAS = tuple(10 * (n + 1) for n in range(CUADROS))
NOMBRE_BASE = "calibracion"


def _px(mm: float, dpi: int) -> int:
    return max(1, round(mm / MM_POR_PULGADA * dpi))


@dataclass(frozen=True)
class Plantilla:
    # capas[i] es el cuadro i + 1: matriz booleana del tamaño del lienzo, True = grabar.
    capas: tuple[np.ndarray, ...]
    # Esquina superior izquierda (x, y) en píxeles de cada cuadro.
    posiciones: tuple[tuple[int, int], ...]
    lado_px: int
    dpi: int
    metodo: str

    @property
    def tamano_mm(self) -> tuple[float, float]:
        alto, ancho = self.capas[0].shape
        return ancho / self.dpi * MM_POR_PULGADA, alto / self.dpi * MM_POR_PULGADA


def crear(dpi: int, metodo: str = tramado.METODO_POR_DEFECTO) -> Plantilla:
    """Arma la plantilla en una cuadrícula de 4 × 2: número a la izquierda, cuadro a la derecha."""
    lado = _px(LADO_MM, dpi)
    zona = _px(ZONA_NUMERO_MM, dpi)
    margen = _px(MARGEN_MM, dpi)
    separacion = _px(SEPARACION_MM, dpi)
    filas = -(-CUADROS // COLUMNAS)
    ancho = 2 * margen + COLUMNAS * (zona + lado) + (COLUMNAS - 1) * separacion
    alto = 2 * margen + filas * lado + (filas - 1) * separacion

    cuadro = _cuadro_tramado(lado, metodo)
    capas = []
    posiciones = []
    for i in range(CUADROS):
        fila, columna = divmod(i, COLUMNAS)
        x = margen + columna * (zona + lado + separacion) + zona
        y = margen + fila * (lado + separacion)
        capa = np.zeros((alto, ancho), np.bool_)
        capa[y : y + lado, x : x + lado] = cuadro
        _dibujar_numero(capa, str(i + 1), x - _px(SEPARACION_NUMERO_MM, dpi), y + lado // 2, dpi)
        capas.append(capa)
        posiciones.append((x, y))
    return Plantilla(tuple(capas), tuple(posiciones), lado, dpi, metodo)


def _cuadro_tramado(lado: int, metodo: str) -> np.ndarray:
    """Degradado de izquierda a derecha con el mismo rango de densidad que una capa tonal."""
    fila = np.linspace(1.0, tramado.DENSIDAD_MINIMA, lado, dtype=np.float32)
    densidades = np.tile(fila, (lado, 1))
    etiquetas = np.full((lado, lado), Capa.NEGRO, np.uint8)
    return tramado.tramar(densidades, etiquetas, metodo)[Capa.NEGRO]


def _dibujar_numero(capa: np.ndarray, texto: str, derecha: int, centro_y: int, dpi: int) -> None:
    """Dibuja el número relleno, alineado a la derecha en `derecha` y centrado en `centro_y`."""
    objetivo = _px(ALTO_NUMERO_MM, dpi)
    # Un trazo extra engrosa el número para que se lea bien grabado en madera.
    grosor = max(1, objetivo // 20)
    fuente = ImageFont.load_default(size=objetivo)
    # Ajusta el tamaño de la fuente para que la altura real del número sea la deseada.
    for _ in range(3):
        izq, arriba, der, abajo = fuente.getbbox(texto, stroke_width=grosor)
        fuente = ImageFont.load_default(size=max(1, round(fuente.size * objetivo / max(abajo - arriba, 1))))
    izq, arriba, der, abajo = fuente.getbbox(texto, stroke_width=grosor)
    lienzo = Image.new("L", (capa.shape[1], capa.shape[0]), 0)
    origen = (derecha - der, centro_y - (arriba + abajo) // 2)
    ImageDraw.Draw(lienzo).text(origen, texto, fill=255, font=fuente, stroke_width=grosor, stroke_fill=255)
    capa |= np.asarray(lienzo) >= 128


def exportar(plantilla: Plantilla, carpeta: str | Path) -> list[Path]:
    """Escribe un BMP por cuadro, todos con el mismo lienzo, más la tabla de potencias."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    archivos = []
    for numero, capa in enumerate(plantilla.capas, start=1):
        ruta = carpeta / f"{NOMBRE_BASE}_{numero}.bmp"
        a_bmp(capa, ruta, plantilla.dpi)
        archivos.append(ruta)

    tabla = carpeta / f"{NOMBRE_BASE}_potencias.txt"
    tabla.write_text(texto_potencias(plantilla, [a.name for a in archivos]), encoding="utf-8")
    archivos.append(tabla)
    return archivos


def texto_potencias(plantilla: Plantilla, nombres: list[str]) -> str:
    ancho_mm, alto_mm = plantilla.tamano_mm
    alto_px, ancho_px = plantilla.capas[0].shape
    intervalo = MM_POR_PULGADA / plantilla.dpi
    lineas = [
        "Plantilla de calibración para RDWorks",
        "",
        f"Ancho: {ancho_mm:.2f} mm",
        f"Alto:  {alto_mm:.2f} mm",
        f"Resolución: {plantilla.dpi} DPI ({ancho_px} x {alto_px} px)",
        f"Intervalo de escaneo: {intervalo:.4f} mm",
        f"Tramado: {plantilla.metodo}",
        f"Cuadros de {LADO_MM:.0f} x {LADO_MM:.0f} mm, del lado denso (izquierda) al lado claro (derecha).",
        "",
        "Potencia sugerida por cuadro:",
        *[
            f"  Cuadro {numero}: {potencia} %  ({nombre})"
            for numero, (potencia, nombre) in enumerate(zip(POTENCIAS, nombres), start=1)
        ],
        "",
        "En RDWorks:",
        "  1. Importa cada BMP y escribe el ancho y alto de arriba (bloquea la proporción).",
        "  2. Coloca todos los BMP en la misma posición X/Y para que queden alineados.",
        "  3. No apliques el tramado de RDWorks (Bitmap Handle): las imágenes ya vienen tramadas.",
        "  4. Deja 'Output direct' y 'Negative engrave' apagados.",
        f"  5. Usa un intervalo de {intervalo:.4f} mm, igual a la resolución de la imagen.",
        "  6. Asigna a cada BMP su propio color (una capa por archivo) y la potencia de la tabla.",
        "  7. Graba y anota qué cuadro da el tono de café que quieres para cada capa tonal.",
        "",
    ]
    return "\n".join(lineas)
