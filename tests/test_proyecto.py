import io
import json
import zipfile

import numpy as np
import pytest
from PIL import Image

from grabado import proyecto
from grabado.exportar import exportar
from grabado.proceso import Ajustes, cargar_foto, procesar
from grabado.proyecto import Proyecto, ProyectoInvalido

ORIENTACION = 0x0112


def foto_jpeg_girada(ruta, ancho=240, alto=160):
    """Un JPEG con textura y la marca EXIF "girar 90°", como los de un celular."""
    rng = np.random.default_rng(3)
    x = np.linspace(0, 1, ancho)
    y = np.linspace(0, 1, alto)[:, None]
    base = 60 + 150 * x * (1 - 0.5 * y) + rng.normal(0, 18, (alto, ancho))
    gris = np.clip(base, 0, 255).astype(np.uint8)
    imagen = Image.fromarray(np.dstack([gris, gris * 0.9, gris * 0.8]).astype(np.uint8), "RGB")
    exif = Image.Exif()
    exif[ORIENTACION] = 6
    imagen.save(ruta, format="JPEG", quality=85, exif=exif)
    return ruta


def mascara_suave(tamano):
    """Blanco = sujeto: un óvalo con el borde en grises, como el que deja la IA."""
    ancho, alto = tamano
    y, x = np.mgrid[0:alto, 0:ancho]
    d = ((x - ancho / 2) / (ancho * 0.35)) ** 2 + ((y - alto / 2) / (alto * 0.4)) ** 2
    return Image.fromarray(np.clip((1.2 - d) * 400, 0, 255).astype(np.uint8), "L")


AJUSTES = Ajustes(
    ancho_mm=61.3,
    dpi=127,
    cortes=(48.5, 101.0, 173.25),
    metodo_tramado="semitono",
    brillo=12,
    contraste=-25,
    nitidez=40,
    contorno=True,
    grosor_contorno_mm=0.7,
)


@pytest.fixture
def ruta_foto(tmp_path):
    return foto_jpeg_girada(tmp_path / "Mi perro.jpg")


def test_guardar_y_abrir_devuelve_lo_mismo(tmp_path, ruta_foto):
    foto = cargar_foto(ruta_foto)
    assert foto.size == (160, 240)  # ya girada
    mascara = mascara_suave(foto.size)
    datos = ruta_foto.read_bytes()
    ruta = tmp_path / "trabajo.grabado"

    proyecto.guardar(ruta, Proyecto("Mi perro.jpg", datos, mascara, AJUSTES))
    abierto = proyecto.abrir(ruta)

    assert abierto.nombre_foto == "Mi perro.jpg"
    assert abierto.foto_datos == datos  # la foto de origen no se recomprime
    assert abierto.ajustes == AJUSTES
    assert np.array_equal(np.asarray(abierto.cargar_foto()), np.asarray(foto))
    assert abierto.mascara.mode == "L"
    assert np.array_equal(np.asarray(abierto.mascara), np.asarray(mascara))


def test_sin_recorte_y_cortes_automaticos(tmp_path, ruta_foto):
    ruta = tmp_path / "p.grabado"
    proyecto.guardar(ruta, Proyecto("Mi perro.jpg", ruta_foto.read_bytes(), None, Ajustes()))
    abierto = proyecto.abrir(ruta)
    assert abierto.mascara is None
    assert abierto.ajustes == Ajustes()
    with zipfile.ZipFile(ruta) as zip_:
        assert "mascara.png" not in zip_.namelist()


def test_guardar_encima_reemplaza_el_archivo(tmp_path, ruta_foto):
    ruta = tmp_path / "p.grabado"
    datos = ruta_foto.read_bytes()
    proyecto.guardar(ruta, Proyecto("Mi perro.jpg", datos, None, Ajustes()))
    proyecto.guardar(ruta, Proyecto("Mi perro.jpg", datos, None, AJUSTES))
    assert proyecto.abrir(ruta).ajustes == AJUSTES
    assert [p.name for p in tmp_path.iterdir()] == ["Mi perro.jpg", "p.grabado"]


def escribir_proyecto(ruta, indice, foto=b"x"):
    with zipfile.ZipFile(ruta, "w") as zip_:
        zip_.writestr("proyecto.json", json.dumps(indice))
        zip_.writestr("foto/a.png", foto)


def test_campos_que_faltan_o_no_se_conocen_quedan_por_defecto(tmp_path):
    ruta = tmp_path / "viejo.grabado"
    escribir_proyecto(ruta, {
        "version": 99,
        "foto": "foto/a.png",
        "algo_nuevo": [1, 2],
        "ajustes": {
            "dpi": 300,
            "cortes": [10, 20, 30],
            "metodo_tramado": "uno_que_no_existe",
            "brillo": "mucho",
            "contorno": 1,
            "campo_del_futuro": True,
        },
    })
    abierto = proyecto.abrir(ruta)
    assert abierto.mascara is None
    assert abierto.ajustes == Ajustes(dpi=300, cortes=(10.0, 20.0, 30.0))


def test_sin_ajustes_todo_por_defecto(tmp_path):
    ruta = tmp_path / "p.grabado"
    escribir_proyecto(ruta, {"foto": "foto/a.png"})
    assert proyecto.abrir(ruta).ajustes == Ajustes()


@pytest.mark.parametrize("contenido", [b"no es un zip", None])
def test_archivo_que_no_es_proyecto(tmp_path, contenido):
    ruta = tmp_path / "malo.grabado"
    if contenido is None:
        with zipfile.ZipFile(ruta, "w") as zip_:
            zip_.writestr("otra_cosa.txt", "hola")
    else:
        ruta.write_bytes(contenido)
    with pytest.raises(ProyectoInvalido):
        proyecto.abrir(ruta)


def exportar_a_bytes(foto, mascara, ajustes, carpeta, nombre):
    archivos = exportar(procesar(foto, ajustes, mascara), carpeta, nombre)
    return {a.name: a.read_bytes() for a in archivos}


def test_exportar_tras_reabrir_da_archivos_identicos(tmp_path, ruta_foto):
    foto = cargar_foto(ruta_foto)
    mascara = mascara_suave(foto.size)
    antes = exportar_a_bytes(foto, mascara, AJUSTES, tmp_path / "antes", ruta_foto.stem)
    assert "Mi perro_4_contorno.bmp" in antes

    ruta = tmp_path / "p.grabado"
    proyecto.guardar(ruta, Proyecto(ruta_foto.name, ruta_foto.read_bytes(), mascara, AJUSTES))
    abierto = proyecto.abrir(ruta)
    nombre = abierto.nombre_foto.rsplit(".", 1)[0]
    despues = exportar_a_bytes(abierto.cargar_foto(), abierto.mascara, abierto.ajustes, tmp_path / "despues", nombre)

    assert despues == antes


def test_la_foto_con_transparencia_se_guarda_tal_cual(tmp_path):
    foto = Image.new("RGBA", (30, 20), (100, 80, 60, 0))
    foto.paste((200, 150, 100, 255), (5, 5, 25, 15))
    png = io.BytesIO()
    foto.save(png, format="PNG")
    ruta = tmp_path / "p.grabado"
    proyecto.guardar(ruta, Proyecto("t.png", png.getvalue(), None, Ajustes()))
    assert np.array_equal(np.asarray(proyecto.abrir(ruta).cargar_foto()), np.asarray(foto))
