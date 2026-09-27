"""Exportación de las capas tramadas como BMP de 1 bit para RDWorks."""

from pathlib import Path

import numpy as np
from PIL import Image

from grabado.proceso import MM_POR_PULGADA, Resultado
from grabado.tonal import Capa

NOMBRES_CAPA = {
    Capa.NEGRO: "1_negro",
    Capa.OSCURO: "2_oscuro",
    Capa.MEDIO: "3_medio",
}

NOMBRE_CONTORNO = "4_contorno"


def a_bmp(grabar: np.ndarray, ruta: Path, dpi: int) -> None:
    """Negro = grabar, blanco = no grabar (fondo, capa Claro y huecos del tramado)."""
    pixeles = np.where(grabar, 0, 255).astype(np.uint8)
    imagen = Image.fromarray(pixeles, "L").convert("1", dither=Image.Dither.NONE)
    imagen.save(ruta, format="BMP", dpi=(dpi, dpi))


def exportar(resultado: Resultado, carpeta: str | Path, nombre_base: str) -> list[Path]:
    """Escribe un BMP por capa grabada, todos con el mismo lienzo, más un archivo con las medidas."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    archivos = []
    for capa, nombre in NOMBRES_CAPA.items():
        ruta = carpeta / f"{nombre_base}_{nombre}.bmp"
        a_bmp(resultado.capas[capa], ruta, resultado.dpi)
        archivos.append(ruta)
    if resultado.contorno is not None:
        ruta = carpeta / f"{nombre_base}_{NOMBRE_CONTORNO}.bmp"
        a_bmp(resultado.contorno, ruta, resultado.dpi)
        archivos.append(ruta)

    medidas = carpeta / f"{nombre_base}_medidas.txt"
    medidas.write_text(texto_medidas(resultado, [a.name for a in archivos]), encoding="utf-8")
    archivos.append(medidas)
    return archivos


def texto_medidas(resultado: Resultado, nombres: list[str]) -> str:
    ancho_mm, alto_mm = resultado.tamano_mm
    alto_px, ancho_px = resultado.gris.shape
    lineas = [
        "Medidas para RDWorks",
        "",
        f"Ancho: {ancho_mm:.2f} mm",
        f"Alto:  {alto_mm:.2f} mm",
        f"Resolución: {resultado.dpi} DPI ({ancho_px} x {alto_px} px)",
        f"Intervalo de escaneo: {MM_POR_PULGADA / resultado.dpi:.4f} mm",
        "",
        "Archivos (de más oscuro a más claro, de mayor a menor potencia):",
        *[f"  - {nombre}" for nombre in nombres],
        "",
        "La capa Claro no se exporta: queda como madera natural.",
        *(
            [
                f"El contorno ({NOMBRE_CONTORNO}) es una línea grabada por dentro del borde del sujeto,",
                "no una línea de corte: grábalo como una capa más, con su propia potencia.",
            ]
            if resultado.contorno is not None
            else []
        ),
        "",
        "En RDWorks:",
        "  1. Importa cada BMP y escribe el ancho y alto de arriba (bloquea la proporción).",
        "  2. Coloca todas las capas en la misma posición X/Y para que queden alineadas.",
        "  3. No apliques el tramado de RDWorks (Bitmap Handle): las imágenes ya vienen tramadas.",
        "  4. Deja 'Output direct' y 'Negative engrave' apagados.",
        f"  5. Usa un intervalo de {MM_POR_PULGADA / resultado.dpi:.4f} mm, igual a la resolución de la imagen.",
        "  6. Asigna a cada capa su color y su potencia.",
        "",
    ]
    return "\n".join(lineas)
