from __future__ import annotations

import os
import sys


def main(argv: list[str] | None = None) -> int:
    if (
        not os.environ.get("DISPLAY")
        and not os.environ.get("WAYLAND_DISPLAY")
        and not os.environ.get("QT_QPA_PLATFORM")
    ):
        print(
            "Nenhuma sessão gráfica detectada (DISPLAY ou WAYLAND_DISPLAY).",
            file=sys.stderr,
        )
        return 1
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print(
            "PyQt6 não está instalado. No Debian: sudo apt install python3-pyqt6",
            file=sys.stderr,
        )
        return 1

    from moah_launcher.actions import LauncherActions
    from moah_launcher.ui.main_window import MainWindow
    from moah_launcher.ui.theme import apply_theme

    application = QApplication(sys.argv if argv is None else argv)
    application.setApplicationName("MOAH Project Launcher")
    application.setOrganizationName("MOAH")
    application.setApplicationDisplayName("MOAH Project Launcher")
    apply_theme(application)
    window = MainWindow(LauncherActions())
    window.show()
    return application.exec()
