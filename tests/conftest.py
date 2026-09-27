import pytest
from PySide6.QtWidgets import QMessageBox


@pytest.fixture(autouse=True)
def descartar_cambios_al_cerrar(monkeypatch):
    """Sin pantalla nadie contesta "¿Guardar los cambios?": al cerrar la ventana se descartan.

    Las pruebas que miran esa pregunta la vuelven a reemplazar.
    """
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Discard)
