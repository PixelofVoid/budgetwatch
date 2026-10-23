from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.ui.formatters import format_money, leftover_color, parse_money
from budgetwatch.ui.layout import CARD_MAX_H, CARD_MIN_H


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(4)
        self.title = QLabel(title)
        self.title.setObjectName("pageTitle")
        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("pageSubtitle")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)


class DashCard(QFrame):
    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
        *,
        expand: bool = True,
    ):
        super().__init__(parent)
        self.setObjectName("dashCard")
        vpolicy = (
            QSizePolicy.Policy.Expanding if expand else QSizePolicy.Policy.Maximum
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, vpolicy)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        self.title = QLabel(title)
        self.title.setObjectName("cardTitle")
        layout.addWidget(self.title)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        layout.addLayout(self.body, 1)


class MetricCard(QFrame):
    def __init__(self, title: str, hint: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(CARD_MIN_H)
        self.setMaximumHeight(CARD_MAX_H)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        self.title = QLabel(title)
        self.title.setObjectName("cardTitle")
        self.value = QLabel("—")
        self.value.setObjectName("cardValue")
        self.value.setWordWrap(False)
        self.hint = QLabel(hint)
        self.hint.setObjectName("cardHint")
        self.hint.setWordWrap(True)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.hint)

    def set_amount(
        self,
        amount: Decimal | None,
        symbol: str,
        *,
        unknown: bool = False,
        unknown_text: str | None = None,
        colorize: bool = False,
    ) -> None:
        from budgetwatch.ui import theme as t

        if unknown or amount is None:
            self.value.setText(unknown_text or "—")
            self.value.setStyleSheet(f"color: {t.AMBER};")
            return
        self.value.setText(format_money(amount, symbol))
        if colorize:
            self.value.setStyleSheet(f"color: {leftover_color(amount)};")
        else:
            self.value.setStyleSheet(f"color: {t.TEXT};")

    def set_hint(self, text: str) -> None:
        self.hint.setText(text)


class WarningBanner(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("warningBanner")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        self.label = QLabel()
        self.label.setObjectName("warningText")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.hide()

    def set_messages(self, messages: list[str]) -> None:
        unique = []
        for msg in messages:
            if msg and msg not in unique:
                unique.append(msg)
        if not unique:
            self.hide()
            return
        self.label.setText("\n".join(f"• {msg}" for msg in unique))
        self.show()


class MoneyEdit(QLineEdit):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setPlaceholderText("0.00")
        self.setAlignment(Qt.AlignmentFlag.AlignRight)

    def amount(self) -> Decimal | None:
        return parse_money(self.text())

    def set_amount(self, value: Decimal | None) -> None:
        if value is None:
            self.clear()
        else:
            self.setText(f"{value:.2f}")


def make_date_edit(value: date | None = None) -> QDateEdit:
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    edit.setDisplayFormat("yyyy-MM-dd")
    if value is None:
        value = date.today()
    edit.setDate(value)
    return edit


def date_from_edit(edit: QDateEdit) -> date:
    qdate = edit.date()
    return date(qdate.year(), qdate.month(), qdate.day())


def confirm_delete(parent: QWidget, title: str, text: str) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(
        QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes
    )
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    return box.exec() == QMessageBox.StandardButton.Yes


def show_error(parent: QWidget, text: str) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle("BudgetWatch")
    box.setText(text)
    box.exec()


def leftover_stylesheet(amount: Decimal | None) -> str:
    from budgetwatch.ui import theme as t

    if amount is None:
        return f"color: {t.AMBER};"
    if amount >= 0:
        return f"color: {t.GREEN}; font-weight: 700;"
    return f"color: {t.RED}; font-weight: 700;"


class LinkHint(QLabel):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.clear_link()

    def set_link(self, occurrence: date | None, unlinked: bool = False) -> None:
        from budgetwatch.ui import theme as t

        if unlinked:
            self.setText("Not linked to a scheduled payday.")
            self.setStyleSheet(f"color: {t.DIM};")
            return
        if occurrence is None:
            self.setText("No nearby scheduled payday to link.")
            self.setStyleSheet(f"color: {t.DIM};")
            return
        self.setText(f"Will link to scheduled payday {occurrence.isoformat()}")
        self.setStyleSheet(f"color: {t.GREEN};")

    def clear_link(self) -> None:
        self.setText("")
