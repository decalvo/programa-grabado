import numpy as np
from PIL import Image

from grabado.exportar import exportar
from grabado.proceso import Ajustes, procesar


def foto_degradado(ancho=300, alto=200):
    fila = np.linspace(0, 255, ancho).astype(np.uint8)
    return Image.fromarray(np.tile(fila, (alto, 1)), "L").convert("RGB")


def test_tamano_final_segun_mm_y_dpi():
    resultado = procesar(foto_degradado(), Ajustes(ancho_mm=100, dpi=254))
    alto, ancho = resultado.gris.shape
    assert ancho == 1000
    assert alto == round(1000 * 200 / 300)
    assert resultado.tamano_mm[0] == 100


def test_exporta_tres_bmp_alineados_de_1_bit(tmp_path):
    resultado = procesar(foto_degradado(), Ajustes(ancho_mm=50, dpi=254))
    archivos = exportar(resultado, tmp_path, "foto")
    bmps = [a for a in archivos if a.suffix == ".bmp"]
    assert [a.name for a in bmps] == ["foto_1_negro.bmp", "foto_2_oscuro.bmp", "foto_3_medio.bmp"]
    tamanos = set()
    for ruta in bmps:
        with Image.open(ruta) as imagen:
            assert imagen.mode == "1"
            assert round(imagen.info["dpi"][0]) == 254
            tamanos.add(imagen.size)
    assert tamanos == {(500, round(500 * 200 / 300))}
    assert (tmp_path / "foto_medidas.txt").read_text(encoding="utf-8").startswith("Medidas para RDWorks")


def test_negro_en_el_bmp_es_grabar(tmp_path):
    resultado = procesar(foto_degradado(), Ajustes(ancho_mm=50, dpi=100))
    exportar(resultado, tmp_path, "foto")
    with Image.open(tmp_path / "foto_1_negro.bmp") as imagen:
        negro = np.asarray(imagen.convert("L")) == 0
    assert (negro == resultado.capas[0]).all()


def test_transparencia_de_la_foto_es_fondo(tmp_path):
    foto = foto_degradado().convert("RGBA")
    alfa = np.zeros((200, 300), np.uint8)
    alfa[:, 100:200] = 255
    foto.putalpha(Image.fromarray(alfa, "L"))
    resultado = procesar(foto, Ajustes(ancho_mm=30, dpi=100))
    grabado_total = resultado.capas[0] | resultado.capas[1] | resultado.capas[2]
    assert not grabado_total[~resultado.mascara].any()
    assert grabado_total[resultado.mascara].any()
