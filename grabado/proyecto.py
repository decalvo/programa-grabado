"""El proyecto: un solo archivo que guarda el trabajo en curso para reabrirlo y volver a exportar.

Es un zip con extensión propia que contiene:

- `proyecto.json`: versión del formato, nombre de la foto de origen y los ajustes.
- `foto/<nombre>`: la foto de origen tal cual se abrió (los bytes del archivo, sin recomprimir).
- `mascara.png`: el recorte retocado (blanco = sujeto), sin pérdida; solo si hay recorte.

Al abrir, la foto se carga igual que la primera vez (con la orientación de la cámara), así
que se obtienen exactamente los mismos píxeles. Los campos que falten (archivos de versiones
anteriores) toman su valor por defecto y los que no se conozcan (versiones posteriores) se ignoran.
"""

import io
import json
import os
import tempfile
import zipfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path, PurePosixPath

from PIL import Image

from grabado import tramado
from grabado.proceso import Ajustes, cargar_foto

EXTENSION = ".grabado"
FILTRO = f"Proyecto de grabado (*{EXTENSION})"
VERSION = 1

_INDICE = "proyecto.json"
_CARPETA_FOTO = "foto"
_MASCARA = "mascara.png"


class ProyectoInvalido(ValueError):
    """El archivo no es un proyecto o está dañado."""


@dataclass(frozen=True)
class Proyecto:
    # Nombre del archivo de la foto de origen; da el nombre base de lo exportado.
    nombre_foto: str
    # Bytes del archivo de la foto de origen, sin modificar.
    foto_datos: bytes
    # Blanco = sujeto, negro = fondo; None = toda la foto es sujeto.
    mascara: Image.Image | None
    ajustes: Ajustes

    def cargar_foto(self) -> Image.Image:
        return cargar_foto(io.BytesIO(self.foto_datos))


def guardar(ruta: str | Path, proyecto: Proyecto) -> None:
    """Escribe el proyecto. Si algo falla, el archivo anterior (si había) queda intacto."""
    ruta = Path(ruta)
    nombre_foto = PurePosixPath(proyecto.nombre_foto.replace("\\", "/")).name or "foto"
    indice = {
        "version": VERSION,
        "foto": f"{_CARPETA_FOTO}/{nombre_foto}",
        "mascara": _MASCARA if proyecto.mascara is not None else None,
        "ajustes": _ajustes_a_json(proyecto.ajustes),
    }
    descriptor, temporal = tempfile.mkstemp(prefix=".", suffix=EXTENSION, dir=ruta.parent)
    try:
        with os.fdopen(descriptor, "wb") as archivo, zipfile.ZipFile(archivo, "w") as zip_:
            zip_.writestr(_INDICE, json.dumps(indice, indent=2, ensure_ascii=False), zipfile.ZIP_DEFLATED)
            # La foto ya viene comprimida (JPEG, PNG…): se guarda tal cual.
            zip_.writestr(indice["foto"], proyecto.foto_datos, zipfile.ZIP_STORED)
            if proyecto.mascara is not None:
                png = io.BytesIO()
                proyecto.mascara.convert("L").save(png, format="PNG")
                zip_.writestr(_MASCARA, png.getvalue(), zipfile.ZIP_STORED)
        os.replace(temporal, ruta)
    except BaseException:
        Path(temporal).unlink(missing_ok=True)
        raise


def abrir(ruta: str | Path) -> Proyecto:
    """Lee un proyecto. Lanza OSError si no se puede leer y ProyectoInvalido si no es un proyecto."""
    try:
        with zipfile.ZipFile(ruta) as zip_:
            indice = json.loads(zip_.read(_INDICE).decode("utf-8"))
            if not isinstance(indice, dict):
                raise ProyectoInvalido("El índice del proyecto no es válido")
            ruta_foto = indice.get("foto")
            if not isinstance(ruta_foto, str):
                raise ProyectoInvalido("El proyecto no tiene foto de origen")
            foto_datos = zip_.read(ruta_foto)
            mascara = None
            ruta_mascara = indice.get("mascara")
            if isinstance(ruta_mascara, str):
                with Image.open(io.BytesIO(zip_.read(ruta_mascara))) as imagen:
                    mascara = imagen.convert("L")
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProyectoInvalido(f"No es un proyecto válido: {error}") from error
    return Proyecto(
        nombre_foto=PurePosixPath(ruta_foto).name,
        foto_datos=foto_datos,
        mascara=mascara,
        ajustes=_ajustes_de_json(indice.get("ajustes")),
    )


def _ajustes_a_json(ajustes: Ajustes) -> dict:
    datos = asdict(ajustes)
    if ajustes.cortes is not None:
        datos["cortes"] = list(ajustes.cortes)
    return datos


def _ajustes_de_json(datos) -> Ajustes:
    """Toma los campos conocidos y válidos; el resto queda con su valor por defecto."""
    if not isinstance(datos, dict):
        return Ajustes()
    por_defecto = Ajustes()
    valores = {}
    for campo in fields(Ajustes):
        if campo.name not in datos:
            continue
        valor = _convertir(campo.name, datos[campo.name], getattr(por_defecto, campo.name))
        if valor is not _INVALIDO:
            valores[campo.name] = valor
    return Ajustes(**valores)


_INVALIDO = object()


def _convertir(nombre: str, valor, por_defecto):
    if nombre == "cortes":
        if valor is None:
            return None
        if (
            isinstance(valor, list)
            and len(valor) == 3
            and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in valor)
        ):
            return tuple(float(c) for c in valor)
        return _INVALIDO
    if nombre == "metodo_tramado":
        return valor if valor in tramado.METODOS else _INVALIDO
    if isinstance(por_defecto, bool):
        return valor if isinstance(valor, bool) else _INVALIDO
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return _INVALIDO
    if isinstance(por_defecto, int):
        return int(valor) if float(valor).is_integer() else _INVALIDO
    return float(valor)
