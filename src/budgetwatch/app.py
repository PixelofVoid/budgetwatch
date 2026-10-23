from __future__ import annotations

import logging
import sys

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from budgetwatch.db.connection import Database
from budgetwatch.db.migrate import DatabaseOpenError
from budgetwatch.services.budget import BudgetService
from budgetwatch.ui.main_window import MainWindow
from budgetwatch.ui.theme import apply_theme


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    QGuiApplication.setDesktopFileName("budgetwatch")
    app = QApplication(sys.argv)
    app.setApplicationName("BudgetWatch")
    app.setApplicationDisplayName("BudgetWatch")
    app.setOrganizationName("BudgetWatch")
    try:
        db = Database.open_default()
    except DatabaseOpenError as exc:
        apply_theme(app, "dark")
        QMessageBox.critical(None, "BudgetWatch", str(exc))
        raise SystemExit(1) from exc

    theme = db.settings.get_value("theme", "dark") or "dark"
    apply_theme(app, theme)
    service = BudgetService(db)
    window = MainWindow(service)
    window.show()
    code = app.exec()
    db.close()
    raise SystemExit(code)
