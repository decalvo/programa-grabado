"""Eliminación del fondo con IA local: de la foto de origen a la máscara del sujeto.

El modelo (rembg sobre onnxruntime) se descarga una sola vez a la carpeta de modelos y
después funciona sin internet. Se intenta la GPU (DirectML) y, si no está disponible o
falla, se usa la CPU.
"""

import os
import threading
from pathlib import Path

import numpy as np
from PIL import Image

# Elegido por calidad de borde en personas y mascotas; ver el PR del ticket #2.
MODELO = "birefnet-general-lite"
TAMANO_MODELO_MB = 224

GPU = "GPU"
CPU = "CPU"
_PROVEEDORES_GPU = ("DmlExecutionProvider", "CUDAExecutionProvider")


def carpeta_modelos() -> Path:
    base = os.environ.get("LOCALAPPDATA") or Path.home()
    return Path(base) / "ProgramaGrabado" / "modelos"


def modelo_descargado(modelo: str = MODELO) -> bool:
    return (carpeta_modelos() / "models" / modelo / f"{modelo}.onnx").exists()


def _marca_sin_gpu(modelo: str) -> Path:
    return carpeta_modelos() / f"{modelo}.sin-gpu"


def binarizar(mascara: Image.Image) -> Image.Image:
    """Máscara en blanco (sujeto) y negro (fondo), sin grises intermedios."""
    return Image.fromarray(np.where(np.asarray(mascara.convert("L")) >= 128, 255, 0).astype(np.uint8))


def _recordar_sin_gpu(modelo: str) -> None:
    try:
        _marca_sin_gpu(modelo).parent.mkdir(parents=True, exist_ok=True)
        _marca_sin_gpu(modelo).touch()
    except OSError:
        pass


class Recortador:
    """Obtiene la máscara del sujeto de una foto: blanco = sujeto, negro = fondo.

    La sesión del modelo se crea la primera vez que se usa y se reutiliza.
    """

    def __init__(self, modelo: str = MODELO, usar_gpu: bool = True) -> None:
        self.modelo = modelo
        # Si la GPU ya falló con este modelo en otra ocasión, no se pierde tiempo reintentando.
        self._usar_gpu = usar_gpu and not _marca_sin_gpu(modelo).exists()
        self._sesion = None
        self._candado = threading.Lock()
        # GPU o CPU según lo que realmente usó la última inferencia; None antes de usarse.
        self.dispositivo: str | None = None

    def __call__(self, foto: Image.Image) -> Image.Image:
        return self.mascara(foto)

    def mascara(self, foto: Image.Image) -> Image.Image:
        with self._candado:
            rgb = foto.convert("RGB")
            if self._sesion is None:
                self._sesion = self._crear_sesion(self._usar_gpu)
            try:
                resultado = self._inferir(rgb)
            except Exception:
                if self.dispositivo != GPU:
                    raise
                # La GPU puede quedarse sin memoria o no soportar el modelo: se reintenta en CPU.
                self._usar_gpu = False
                _recordar_sin_gpu(self.modelo)
                self._sesion = self._crear_sesion(False)
                resultado = self._inferir(rgb)
            return binarizar(resultado)

    def _inferir(self, foto: Image.Image) -> Image.Image:
        from rembg import remove

        mascara = remove(foto, session=self._sesion, only_mask=True)
        if mascara.size != foto.size:
            mascara = mascara.resize(foto.size, Image.Resampling.BILINEAR)
        return mascara

    def _crear_sesion(self, usar_gpu: bool):
        os.environ.setdefault("U2NET_HOME", str(carpeta_modelos()))
        import onnxruntime as ort
        from rembg import new_session

        ort.set_default_logger_severity(4)  # Sin avisos de onnxruntime en la consola.
        disponibles = ort.get_available_providers()
        proveedores = [p for p in _PROVEEDORES_GPU if usar_gpu and p in disponibles]
        proveedores.append("CPUExecutionProvider")
        opciones = ort.SessionOptions()
        # DirectML no admite patrones de memoria ni ejecución en paralelo.
        opciones.enable_mem_pattern = False
        opciones.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        try:
            sesion = new_session(self.modelo, sess_opts=opciones, providers=proveedores)
        except Exception:
            if len(proveedores) == 1:
                raise
            sesion = new_session(self.modelo, sess_opts=opciones, providers=["CPUExecutionProvider"])
        activos = sesion.inner_session.get_providers()
        self.dispositivo = GPU if any(p in _PROVEEDORES_GPU for p in activos) else CPU
        return sesion
