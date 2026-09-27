import os
import sys
import types

import numpy as np
import pytest
from PIL import Image

from grabado import fondo
from grabado.exportar import exportar
from grabado.proceso import Ajustes, procesar


def foto_con_sujeto(ancho=120, alto=80):
    """Fondo claro y un sujeto oscuro en el centro; devuelve la foto y la máscara real."""
    datos = np.full((alto, ancho, 3), 230, np.uint8)
    sujeto = np.zeros((alto, ancho), bool)
    sujeto[20:60, 40:80] = True
    datos[20:60, 40:80] = np.linspace(0, 200, 40, dtype=np.uint8)[None, :, None]
    return Image.fromarray(datos, "RGB"), sujeto


class SesionFalsa:
    def __init__(self, proveedores, falla=False):
        self.proveedores = proveedores
        self.falla = falla
        self.inner_session = types.SimpleNamespace(get_providers=lambda: list(proveedores))


@pytest.fixture
def rembg_falso(monkeypatch, tmp_path):
    """Sustituye rembg: la GPU falla al inferir; la máscara es un rectángulo gris (suave)."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("U2NET_HOME", str(tmp_path / "u2net"))
    creadas = []

    def new_session(modelo, sess_opts=None, providers=None):
        sesion = SesionFalsa(providers, falla="DmlExecutionProvider" in providers)
        creadas.append(sesion)
        return sesion

    def remove(foto, session, only_mask):
        assert only_mask
        if session.falla:
            raise RuntimeError("sin memoria en la GPU")
        mascara = np.zeros((foto.height // 2, foto.width // 2), np.uint8)
        mascara[10:30, 20:40] = 200  # Otro tamaño y valores no binarios, como un modelo real.
        return Image.fromarray(mascara, "L")

    monkeypatch.setitem(sys.modules, "rembg", types.SimpleNamespace(new_session=new_session, remove=remove))
    import onnxruntime

    monkeypatch.setattr(
        onnxruntime, "get_available_providers", lambda: ["DmlExecutionProvider", "CPUExecutionProvider"]
    )
    return creadas


def test_binarizar_deja_solo_blanco_y_negro():
    gris = Image.fromarray(np.array([[0, 127, 128, 255]], np.uint8), "L")
    assert np.asarray(fondo.binarizar(gris)).tolist() == [[0, 0, 255, 255]]


def test_mascara_del_tamano_de_la_foto_y_binaria(rembg_falso):
    foto, _ = foto_con_sujeto()
    mascara = fondo.Recortador(usar_gpu=False)(foto)
    assert mascara.mode == "L"
    assert mascara.size == foto.size
    assert set(np.unique(np.asarray(mascara))) == {0, 255}
    assert fondo.Recortador(usar_gpu=False).dispositivo is None


def test_si_la_gpu_falla_usa_la_cpu(rembg_falso):
    foto, _ = foto_con_sujeto()
    recortador = fondo.Recortador(usar_gpu=True)
    mascara = recortador(foto)
    assert recortador.dispositivo == fondo.CPU
    assert [s.proveedores[0] for s in rembg_falso] == ["DmlExecutionProvider", "CPUExecutionProvider"]
    assert np.asarray(mascara).any()
    # La siguiente foto ya va directo a la CPU.
    recortador(foto)
    assert len(rembg_falso) == 2
    # Y la próxima vez que se abra el programa tampoco se reintenta la GPU con este modelo.
    fondo.Recortador(usar_gpu=True)(foto)
    assert rembg_falso[-1].proveedores == ["CPUExecutionProvider"]


def test_error_en_cpu_se_propaga(rembg_falso, monkeypatch):
    monkeypatch.setattr(
        sys.modules["rembg"], "remove", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("roto"))
    )
    with pytest.raises(RuntimeError, match="roto"):
        fondo.Recortador(usar_gpu=False)(foto_con_sujeto()[0])


def test_carpeta_de_modelos_en_localappdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert fondo.carpeta_modelos() == tmp_path / "ProgramaGrabado" / "modelos"
    assert not fondo.modelo_descargado("modelo")
    (tmp_path / "ProgramaGrabado" / "modelos" / "models" / "modelo").mkdir(parents=True)
    (tmp_path / "ProgramaGrabado" / "modelos" / "models" / "modelo" / "modelo.onnx").touch()
    assert fondo.modelo_descargado("modelo")


def test_con_mascara_el_fondo_queda_blanco_en_los_bmp(tmp_path):
    foto, sujeto = foto_con_sujeto()
    mascara = Image.fromarray(np.where(sujeto, 255, 0).astype(np.uint8), "L")
    resultado = procesar(foto, Ajustes(ancho_mm=120 / 254 * 25.4, dpi=254), mascara)
    exportar(resultado, tmp_path, "foto")
    for nombre in ("foto_1_negro.bmp", "foto_2_oscuro.bmp", "foto_3_medio.bmp"):
        with Image.open(tmp_path / nombre) as bmp:
            blanco = np.asarray(bmp.convert("L")) == 255
        assert blanco[~sujeto].all()
    # Los cortes automáticos miran solo el sujeto: con el fondo claro incluido, el corte
    # Medio/Claro quedaría mucho más arriba.
    assert resultado.cortes[2] < 200


@pytest.mark.skipif(
    not os.environ.get("GRABADO_PRUEBAS_LENTAS") or not fondo.modelo_descargado(),
    reason="Prueba lenta con el modelo real: GRABADO_PRUEBAS_LENTAS=1 y el modelo descargado",
)
def test_modelo_real_recorta_al_sujeto():
    from skimage import data

    foto = Image.fromarray(data.astronaut())  # Dominio público (NASA).
    recortador = fondo.Recortador()
    mascara = np.asarray(recortador(foto)) == 255
    assert recortador.dispositivo in (fondo.GPU, fondo.CPU)
    assert mascara[150, 250]  # La cara.
    assert not mascara[20, 20]  # Esquina del fondo.
