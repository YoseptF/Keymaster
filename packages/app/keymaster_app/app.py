from __future__ import annotations

import sys

from keymaster_app import settings
from keymaster_app.i18n import Translator, install, t


def main(argv: list[str] | None = None) -> int:
    resolved = settings.resolve()
    install(Translator(resolved.language, core_dir=resolved.core))
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        sys.stderr.write(t("app.launch.no_qt") + "\n")
        return 1
    from keymaster_app.ui.main_window import MainWindow
    from keymaster_app.ui.theme import apply_theme

    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName("keymaster-app")
    app.setDesktopFileName("keymaster-app")
    apply_theme(app)
    window = MainWindow()
    window.show()
    if argv:
        window.add_paths(list(argv))
    if settings.core_problem(resolved):
        window.show_setup_check()
    return app.exec()
