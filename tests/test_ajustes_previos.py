import numpy as np
import pytest
from PIL import Image

from grabado import ajustes_previos as ap
from grabado.proceso import Ajustes, procesar
from grabado.simulacion import dpi_para_caja, simular
from grabado.tonal import Capa


def degradado(ancho=256, alto=40):
    return np.tile(np.arange(ancho, dtype=np.float32), (alto, 1))


def foto_plana(ancho=300, alto=200, semilla=0):
    """Foto de celular 'plana': tonos entre 100 y 160, con algo de detalle."""
    rng = np.random.default_rng(semilla)
    base = np.linspace(100, 160, ancho)[None, :] + rng.normal(0, 4, (alto, ancho))
    return Image.fromarray(base.clip(0, 255).astype(np.uint8), "L")


def test_valores_neutros_no_cambian_la_imagen():
    rng = np.random.default_rng(1)
    gris = rng.integers(0, 256, (50, 60)).astype(np.float32)
    mascara = rng.random((50, 60)) > 0.5
    assert np.array_equal(ap.aplicar(gris), gris)
    assert np.array_equal(ap.aplicar(gris, 0, 0, 0, 254, mascara), gris)
    assert np.array_equal(procesar(Image.fromarray(gris.astype(np.uint8)), Ajustes(ancho_mm=60 / 10)).gris, gris)


def test_brillo_desplaza_los_tonos():
    gris = degradado()
    mas = ap.aplicar(gris, brillo=40)
    assert np.allclose(mas[:, 50:200], gris[:, 50:200] + 40)
    assert mas.max() == 255  # recorta sin pasarse
    menos = ap.aplicar(gris, brillo=-40)
    assert menos.mean() < gris.mean() - 30 and menos.min() == 0


def test_contraste_separa_o_junta_los_tonos_alrededor_del_gris_medio():
    gris = np.array([[100.0, 128.0, 156.0]], np.float32)
    assert np.allclose(ap.aplicar(gris, contraste=50), [[72, 128, 184]])  # ×2
    assert np.allclose(ap.aplicar(gris, contraste=-50), [[114, 128, 142]])  # ×0,5
    assert ap.aplicar(degradado(), contraste=100).std() > degradado().std()


def test_nitidez_realza_un_borde_sin_moverlo():
    gris = np.full((40, 40), 100.0, np.float32)
    gris[:, 20:] = 150
    nitida = ap.aplicar(gris, nitidez=100, dpi=254)
    assert nitida[:, 19].mean() < 100 and nitida[:, 20].mean() > 150
    # Lejos del borde no cambia.
    assert np.allclose(nitida[:, :5], 100) and np.allclose(nitida[:, -5:], 150)


def test_nitidez_mide_lo_mismo_en_mm_a_cualquier_resolucion():
    def perfil(dpi):
        px = round(dpi / 254 * 60)
        gris = np.full((10, px), 100.0, np.float32)
        gris[:, px // 2 :] = 150
        return ap.aplicar(gris, nitidez=100, dpi=dpi)[5]

    fina, gruesa = perfil(254), perfil(508)
    # El halo ocupa los mismos mm: el doble de píxeles con el doble de DPI.
    ancho_halo = lambda p: int((np.abs(np.diff(p)) > 0.5).sum())  # noqa: E731
    assert abs(ancho_halo(gruesa) - 2 * ancho_halo(fina)) <= 2


def test_nitidez_con_mascara_no_deja_halo_del_fondo_en_el_sujeto():
    gris = np.full((40, 40), 120.0, np.float32)
    gris[:, :20] = 255  # fondo blanco
    mascara = np.zeros((40, 40), bool)
    mascara[:, 20:] = True
    nitida = ap.aplicar(gris, nitidez=200, dpi=254, mascara=mascara)
    assert np.allclose(nitida[mascara], 120)
    # Sin máscara el fondo blanco oscurece el borde del sujeto.
    assert ap.aplicar(gris, nitidez=200, dpi=254)[:, 20].mean() < 110


def test_auto_mejorar_estira_una_foto_plana():
    gris = np.asarray(foto_plana(), np.float32)
    valores = ap.auto_mejorar(gris)
    assert valores["contraste"] > 50 and valores["nitidez"] > 0
    mejorada = ap.aplicar(gris, valores["brillo"], valores["contraste"])
    bajo, alto = np.percentile(mejorada, [1, 99])
    assert bajo < 20 and alto > 235
    assert abs(np.median(mejorada) - 128) < 15


def test_auto_mejorar_no_baja_el_contraste_de_una_foto_que_ya_lo_tiene():
    valores = ap.auto_mejorar(degradado())
    assert valores["contraste"] == 0 and abs(valores["brillo"]) <= 1


def test_auto_mejorar_solo_mira_el_sujeto():
    gris = np.asarray(foto_plana(), np.float32).copy()
    mascara = np.zeros(gris.shape, bool)
    mascara[:, 100:200] = True
    fondo = gris.copy()
    fondo[:, :100] = 0
    fondo[:, 200:] = 255
    assert ap.auto_mejorar(fondo, mascara) == ap.auto_mejorar(gris[mascara])
    assert ap.auto_mejorar(fondo, mascara)["contraste"] > ap.auto_mejorar(fondo)["contraste"]


def test_auto_mejorar_foto_usa_la_mascara_de_la_foto():
    foto = foto_plana()
    mascara = Image.new("L", foto.size, 0)
    mascara.paste(255, (100, 0, 200, foto.height))
    con = ap.auto_mejorar_foto(foto, mascara)
    sujeto = np.asarray(foto, np.float32)[:, 100:200]
    assert abs(con["contraste"] - ap.auto_mejorar(sujeto)["contraste"]) <= 2


def test_la_exportacion_usa_la_foto_ajustada_y_recalcula_los_cortes_automaticos():
    foto = foto_plana()
    ajustes = Ajustes(ancho_mm=30, dpi=254)
    neutro = procesar(foto, ajustes)
    mejorado = procesar(foto, Ajustes(ancho_mm=30, dpi=254, **ap.auto_mejorar_foto(foto)))
    assert mejorado.gris.std() > 2 * neutro.gris.std()
    # Los cortes automáticos siguen a la foto ajustada: se abren con ella.
    assert mejorado.cortes[2] - mejorado.cortes[0] > 2 * (neutro.cortes[2] - neutro.cortes[0])
    # Con cortes elegidos a mano, se respetan.
    manual = procesar(foto, Ajustes(ancho_mm=30, dpi=254, cortes=(60.0, 120.0, 180.0), brillo=30))
    assert manual.cortes == (60.0, 120.0, 180.0)


def test_el_brillo_cambia_la_capa_de_los_pixeles_con_cortes_a_mano():
    foto = foto_plana()
    cortes = (110.0, 130.0, 150.0)
    oscuro = procesar(foto, Ajustes(ancho_mm=30, cortes=cortes, brillo=-30))
    claro = procesar(foto, Ajustes(ancho_mm=30, cortes=cortes, brillo=30))
    assert (oscuro.etiquetas == Capa.NEGRO).sum() > (claro.etiquetas == Capa.NEGRO).sum()
    assert (claro.etiquetas == Capa.CLARO).sum() > (oscuro.etiquetas == Capa.CLARO).sum()


@pytest.mark.parametrize("valores", [{"brillo": 25, "contraste": 60, "nitidez": 100}, {"contraste": -40}])
def test_vista_previa_y_exportacion_coinciden(valores):
    """La vista previa (a menos DPI) reparte las capas casi igual que la exportación."""
    rng = np.random.default_rng(3)
    base = rng.normal(130, 25, (120, 160)).clip(0, 255).astype(np.uint8)
    foto = Image.fromarray(base, "L").resize((1600, 1200), Image.Resampling.BICUBIC)
    ajustes = Ajustes(ancho_mm=100, dpi=254, **valores)
    completo = procesar(foto, ajustes)
    dpi = dpi_para_caja(foto.size, 100, 254, (500, 500))
    reducido = procesar(foto, Ajustes(ancho_mm=100, dpi=dpi, **valores))
    assert np.allclose(completo.cortes, reducido.cortes, atol=3)
    for capa in Capa:
        parte_completa = (completo.etiquetas == capa).mean()
        parte_reducida = (reducido.etiquetas == capa).mean()
        assert abs(parte_completa - parte_reducida) < 0.03
    assert simular(reducido).size == reducido.etiquetas.shape[::-1]
