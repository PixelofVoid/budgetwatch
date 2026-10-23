from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.db.connection import DATA_DIR
from budgetwatch.services.budget import BudgetService, ValidationError
from budgetwatch.ui.layout import page_margins
from budgetwatch.ui.theme import apply_theme
from budgetwatch.ui.widgets import MoneyEdit, PageHeader, show_error

SETTINGS_MAX = 860
FIELD_MIN = 280


def _slash_wrap(path: str) -> str:
    return str(path).replace("/", "/\u200b")


class SettingsPage(QWidget):
    def __init__(self, service: BudgetService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        page_margins(layout)
        layout.setSpacing(16)

        self.stack = QWidget()
        self.stack.setMaximumWidth(SETTINGS_MAX)
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        col = QVBoxLayout(self.stack)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(16)
        col.addWidget(PageHeader("Settings", "Offline. Data stays on this computer."))

        self.household_box = QGroupBox("Household")
        self.household_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        grid = QGridLayout(self.household_box)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        grid.setColumnMinimumWidth(0, 180)
        grid.setColumnMinimumWidth(1, FIELD_MIN)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        self.window_days = QLineEdit()
        self.window_days.setMinimumWidth(FIELD_MIN)
        self.window_days.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.savings = MoneyEdit()
        self.savings.setMinimumWidth(FIELD_MIN)
        self.savings.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.other = MoneyEdit()
        self.other.setMinimumWidth(FIELD_MIN)
        self.other.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.symbol = QLineEdit()
        self.symbol.setMaxLength(4)
        self.symbol.setMinimumWidth(FIELD_MIN)
        self.symbol.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.dark = QCheckBox("Enabled")
        self.dark.setObjectName("themeToggle")
        self.dark.setToolTip("Dark grey window with orange buttons. Default on.")
        rows = [
            ("Average window (days)", self.window_days),
            ("Monthly savings target", self.savings),
            ("Other monthly spending", self.other),
            ("Currency symbol", self.symbol),
            ("Dark theme", self.dark),
        ]
        for i, (text, field) in enumerate(rows):
            lab = QLabel(text)
            lab.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(lab, i, 0)
            grid.addWidget(field, i, 1)
        self.dark.toggled.connect(self._toggle_theme)
        self.save_btn = QPushButton("Save settings")
        self.save_btn.setObjectName("primary")
        self.save_btn.setMinimumHeight(36)
        self.save_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.save_btn.clicked.connect(self.save_focused)
        grid.addWidget(self.save_btn, len(rows), 1)
        col.addWidget(self.household_box)

        self.data_box = QGroupBox("Local data")
        self.data_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        db_layout = QVBoxLayout(self.data_box)
        db_layout.setSpacing(10)
        db_layout.addWidget(QLabel("Database path"))
        self.db_path = QLabel()
        self.db_path.setObjectName("monoPath")
        self.db_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.db_path.setWordWrap(True)
        self.db_path.setTextFormat(Qt.TextFormat.PlainText)
        self.db_path.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.db_path.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        db_layout.addWidget(self.db_path)
        db_layout.addWidget(QLabel("Backup folder"))
        self.backup_path = QLabel()
        self.backup_path.setObjectName("monoPath")
        self.backup_path.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.backup_path.setWordWrap(True)
        self.backup_path.setTextFormat(Qt.TextFormat.PlainText)
        self.backup_path.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.backup_path.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        db_layout.addWidget(self.backup_path)
        self.export_btn = QPushButton("Export CSV")
        self.export_btn.setObjectName("primary")
        self.export_btn.setMinimumHeight(40)
        self.export_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.export_btn.clicked.connect(self._export)
        db_layout.addWidget(self.export_btn)
        self.help_note = QLabel(
            "Offline. Data stays on this computer. Before schema changes, "
            "BudgetWatch copies the live file into the backup folder."
        )
        self.help_note.setWordWrap(True)
        self.help_note.setObjectName("helperText")
        self.help_note.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        db_layout.addWidget(self.help_note)
        col.addWidget(self.data_box)
        col.addStretch(1)

        layout.addWidget(self.stack, 0)
        layout.addStretch(1)

    def refresh(self) -> None:
        settings = self.service.get_settings()
        self.window_days.setText(str(settings.average_window_days))
        self.savings.set_amount(settings.savings_target_monthly)
        self.symbol.setText(settings.currency_symbol)
        self.other.set_amount(self.service.other_monthly_spending())
        self.dark.blockSignals(True)
        self.dark.setChecked(self.service.theme_name() == "dark")
        self.dark.blockSignals(False)
        self.db_path.setText(_slash_wrap(str(self.service.db_path())))
        self.backup_path.setText(_slash_wrap(str(DATA_DIR / "backups")))

    def save_focused(self) -> None:
        try:
            days = int(self.window_days.text().strip())
        except ValueError:
            show_error(self, "Average window must be a whole number of days.")
            return
        savings = self.savings.amount()
        if savings is None:
            savings = 0
        other = self.other.amount()
        if other is None:
            other = 0
        try:
            self.service.update_settings(
                average_window_days=days,
                savings_target_monthly=savings,
                currency_symbol=self.symbol.text(),
            )
            self.service.set_other_monthly_spending(other)
            self.service.set_theme_name("dark" if self.dark.isChecked() else "light")
        except ValidationError as exc:
            show_error(self, str(exc))

    def _toggle_theme(self, dark: bool) -> None:
        name = "dark" if dark else "light"
        self.service.set_theme_name(name)
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, name)
        window = self.window()
        if hasattr(window, "refresh_all"):
            window.refresh_all()

    def _export(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Export CSV folder",
            "",
            QFileDialog.Option.DontUseNativeDialog,
        )
        if not directory:
            return
        paths = self.service.export_csv(directory)
        names = ", ".join(p.name for p in paths)
        QMessageBox.information(self, "Export complete", f"Wrote {names} to {directory}")

    def new_item(self) -> None:
        return

    def focus_default(self) -> None:
        self.window_days.setFocus()
