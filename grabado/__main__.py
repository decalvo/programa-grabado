import sys

from PySide6.QtWidgets import QApplication

from grabado.ui.ventana import Ventana


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Programa grabado")
    ventana = Ventana()
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
