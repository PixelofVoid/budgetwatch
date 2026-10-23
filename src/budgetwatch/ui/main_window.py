from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, QRect, QSize, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.services.budget import BudgetService
from budgetwatch.services.bus import DataBus
from budgetwatch.ui.cashflow_page import CashFlowPage
from budgetwatch.ui.dashboard_page import DashboardPage
from budgetwatch.ui.income_page import IncomePage
from budgetwatch.ui.layout import DRAWER_WIDTH, NAV_WIDTH
from budgetwatch.ui.plan_page import PlanPage
from budgetwatch.ui.recurring_page import RecurringPage
from budgetwatch.ui.settings_page import SettingsPage
from budgetwatch.ui.transactions_page import TransactionsPage
from budgetwatch.ui.upcoming_bills import UpcomingBillsPanel

NAV_ITEMS = [
    ("Dashboard", "▦"),
    ("Plan", "▤"),
    ("Income", "$"),
    ("Recurring", "↻"),
    ("Cash flow", "▯"),
    ("Transactions", "≡"),
    ("Settings", "⚙"),
]


class QtDataBridge(QObject):
    dataChanged = Signal()

    def __init__(self, bus: DataBus, parent: QObject | None = None):
        super().__init__(parent)
        bus.subscribe(self._emit)

    def _emit(self) -> None:
        self.dataChanged.emit()


class SideNav(QFrame):
    pageRequested = Signal(int)
    billsToggled = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("sideNav")
        self.setFixedWidth(NAV_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 16)
        layout.setSpacing(4)
        brand = QLabel("BudgetWatch")
        brand.setObjectName("brand")
        sub = QLabel("Offline household")
        sub.setObjectName("brandSub")
        layout.addWidget(brand)
        layout.addWidget(sub)
        layout.addSpacing(16)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: list[QPushButton] = []
        for index, (name, icon) in enumerate(NAV_ITEMS):
            btn = QPushButton(f"{icon}  {name}")
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=index: self.pageRequested.emit(i))
            self.group.addButton(btn, index)
            self.buttons.append(btn)
            layout.addWidget(btn)
        self.buttons[0].setChecked(True)
        layout.addStretch(1)
        self.upcoming_btn = QPushButton("Upcoming bills")
        self.upcoming_btn.setObjectName("drawerToggle")
        self.upcoming_btn.setCheckable(True)
        self.upcoming_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.upcoming_btn.setToolTip("Ctrl+B")
        self.upcoming_btn.clicked.connect(self.billsToggled.emit)
        layout.addWidget(self.upcoming_btn)

    def set_page(self, index: int) -> None:
        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)


class MainWindow(QMainWindow):
    def __init__(self, service: BudgetService):
        super().__init__()
        self.service = service
        self.setWindowTitle("BudgetWatch")
        self.setMinimumSize(960, 640)

        self.nav = SideNav()
        self.stack = QStackedWidget()
        self.dashboard = DashboardPage(service)
        self.plan = PlanPage(service)
        self.income = IncomePage(service)
        self.recurring = RecurringPage(service)
        self.cashflow = CashFlowPage(service)
        self.transactions = TransactionsPage(service)
        self.settings = SettingsPage(service)
        for page in (
            self.dashboard,
            self.plan,
            self.income,
            self.recurring,
            self.cashflow,
            self.transactions,
            self.settings,
        ):
            self.stack.addWidget(page)

        self.drawer = UpcomingBillsPanel(service)
        self.drawer.hide()
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.stack)
        self.splitter.addWidget(self.drawer)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setChildrenCollapsible(False)
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.nav)
        root.addWidget(self.splitter, 1)
        self.setCentralWidget(central)

        self.status = QLabel()
        self.statusBar().addPermanentWidget(self.status, 1)

        self._did_initial_focus = False
        self.nav.pageRequested.connect(self._show_page)
        self.nav.billsToggled.connect(self.toggle_upcoming_bills)

        self.bridge = QtDataBridge(service.bus, self)
        self.bridge.dataChanged.connect(
            self.refresh_all, Qt.ConnectionType.QueuedConnection
        )
        self.refresh_all()
        self._restore_geometry()

        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._new_item)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._save_focused)
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self.toggle_upcoming_bills)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self._escape)
        for index in range(len(NAV_ITEMS)):
            QShortcut(
                QKeySequence(f"Ctrl+{index + 1}"),
                self,
                activated=lambda i=index: self._show_page(i),
            )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._did_initial_focus:
            self._did_initial_focus = True
            page = self.stack.currentWidget()
            if hasattr(page, "focus_default"):
                page.focus_default()

    @Slot()
    def refresh_all(self) -> None:
        self.dashboard.refresh()
        self.plan.refresh()
        self.income.refresh()
        self.recurring.refresh()
        self.cashflow.refresh()
        self.transactions.refresh()
        self.settings.refresh()
        self.drawer.refresh()
        path = self.service.db_path()
        self.status.setText(f"Offline · {path}")

    def _current_page(self):
        return self.stack.currentWidget()

    @Slot(int)
    def _show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.nav.set_page(index)
        page = self.stack.currentWidget()
        if hasattr(page, "focus_default"):
            page.focus_default()

    @Slot()
    def toggle_upcoming_bills(self) -> None:
        visible = not self.drawer.isVisible()
        self.drawer.setVisible(visible)
        self.nav.upcoming_btn.setChecked(visible)
        if visible:
            total = max(self.splitter.size().width(), 1)
            self.splitter.setSizes([max(total - DRAWER_WIDTH, 400), DRAWER_WIDTH])
            self.drawer.refresh()
        else:
            self.splitter.setSizes([self.splitter.size().width(), 0])

    @Slot()
    def _new_item(self) -> None:
        page = self._current_page()
        if hasattr(page, "new_item"):
            page.new_item()

    @Slot()
    def _save_focused(self) -> None:
        page = self._current_page()
        if hasattr(page, "save_focused"):
            page.save_focused()

    @Slot()
    def _escape(self) -> None:
        widget = self.focusWidget()
        if widget is not None:
            window = widget.window()
            if window is not self:
                window.close()
                return
        if self.drawer.isVisible():
            self.toggle_upcoming_bills()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_geometry()
        super().closeEvent(event)

    def _restore_geometry(self) -> None:
        width = _pref_int(self.service.get_pref("window_w"), 1200)
        height = _pref_int(self.service.get_pref("window_h"), 760)
        width = max(960, min(width, 2400))
        height = max(640, min(height, 1600))
        self.resize(QSize(width, height))
        x = self.service.get_pref("window_x")
        y = self.service.get_pref("window_y")
        if x is not None and y is not None:
            point = QPoint(int(x), int(y))
            if _point_on_screen(point, QSize(width, height)):
                self.move(point)
        if self.service.get_pref("window_maximized") == "1":
            self.showMaximized()

    def _save_geometry(self) -> None:
        geo = self.normalGeometry() if self.isMaximized() else self.geometry()
        self.service.set_pref("window_x", str(geo.x()))
        self.service.set_pref("window_y", str(geo.y()))
        self.service.set_pref("window_w", str(geo.width()))
        self.service.set_pref("window_h", str(geo.height()))
        self.service.set_pref("window_maximized", "1" if self.isMaximized() else "0")


def _pref_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _point_on_screen(point: QPoint, size: QSize) -> bool:
    rect = QRect(point, size)
    for screen in QGuiApplication.screens():
        if screen.availableGeometry().intersects(rect):
            return True
    return False
