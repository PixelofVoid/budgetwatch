import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from budgetwatch.db.schema import DEFAULT_SETTINGS
from budgetwatch.ui.chart import SurplusChart
from budgetwatch.ui.dashboard_page import DashboardPage
from budgetwatch.ui.formatters import leftover_color
from budgetwatch.ui.main_window import NAV_ITEMS
from budgetwatch.ui.settings_page import FIELD_MIN, SETTINGS_MAX, SettingsPage, _slash_wrap
from budgetwatch.ui.theme import ACCENT, DARK, apply_theme, stylesheet


def _app():
    return QApplication.instance() or QApplication([])


def test_dark_palette_matches_spec():
    assert DARK["BG"] == "#1B1B1F"
    assert DARK["NAV_BG"] == "#141416"
    assert DARK["SURFACE"] == "#2A2A30"
    assert DARK["SURFACE_2"] == "#333338"
    assert DARK["BORDER"] == "#3F3F46"
    assert DARK["TEXT"] == "#F4F4F5"
    assert DARK["MUTED"] == "#A1A1AA"
    assert DARK["ACCENT"] == "#F97316"
    assert DARK["ACCENT_HOVER"] == "#EA580C"
    assert DARK["GREEN"] == "#34D399"
    assert DARK["RED"] == "#FB7185"
    css = stylesheet()
    assert "#F97316" in css
    assert "#0D9488" not in css
    assert "#14B8A6" not in css


def test_theme_defaults_dark():
    assert DEFAULT_SETTINGS["theme"] == "dark"


def test_nav_page_list_unchanged():
    assert [name for name, _icon in NAV_ITEMS] == [
        "Dashboard",
        "Plan",
        "Income",
        "Recurring",
        "Cash flow",
        "Transactions",
        "Settings",
    ]


def test_slash_wrap_breaks_at_slashes_only():
    wrapped = _slash_wrap("/home/roni/.local/share/budgetwatch/budgetwatch.db")
    assert "\u200b" in wrapped
    assert wrapped.replace("\u200b", "") == "/home/roni/.local/share/budgetwatch/budgetwatch.db"
    assert "budgetwatch.\u200bdb" not in wrapped


def test_leftover_color_follows_theme():
    app = _app()
    apply_theme(app, "dark")
    assert leftover_color(1) == "#34D399"
    assert leftover_color(-1) == "#FB7185"
    apply_theme(app, "light")
    assert leftover_color(1) == "#059669"
    apply_theme(app, "dark")
    assert leftover_color(1) == "#34D399"


def test_dashboard_cards_fill_main_pane(service):
    app = _app()
    apply_theme(app, "dark")
    page = DashboardPage(service)
    page.resize(900, 860)
    page.show()
    app.processEvents()
    pair_width = page.cash_card.width() + page.plan_card.width()
    assert abs(page.cash_card.width() - page.plan_card.width()) <= 2
    assert pair_width >= 900 - 48 - 16 - 8
    assert page.cash_card.width() > 380
    assert page.cash_card.height() >= 140
    assert page.left_card.height() >= 160
    assert page.cat_card.height() >= 360
    assert page.chart_card.height() >= 360
    assert page.chart.width() >= page.chart_card.width() - 48
    page.close()


def test_settings_uses_page_width_not_phone_stub(service):
    app = _app()
    apply_theme(app, "dark")
    page = SettingsPage(service)
    page.resize(900, 800)
    page.show()
    page.refresh()
    app.processEvents()
    assert page.stack.maximumWidth() == SETTINGS_MAX
    assert page.stack.width() >= 800
    assert page.household_box.width() >= 800
    assert page.data_box.width() >= 800
    assert page.window_days.width() >= FIELD_MIN
    assert page.export_btn.height() >= 36
    assert page.export_btn.width() >= 400
    export_geom = page.export_btn.geometry()
    help_geom = page.help_note.geometry()
    assert not export_geom.intersects(help_geom)
    assert help_geom.top() >= export_geom.bottom()
    assert page.dark.isChecked()
    page.close()


def test_all_nav_pages_open_in_dark_theme(service):
    app = _app()
    apply_theme(app, "dark")
    from budgetwatch.ui.main_window import MainWindow

    win = MainWindow(service)
    win.resize(1200, 800)
    win.show()
    app.processEvents()
    assert win.nav.buttons[0].isChecked()
    for index, (name, _icon) in enumerate(NAV_ITEMS):
        win._show_page(index)
        app.processEvents()
        page = win.stack.currentWidget()
        assert page is not None
        assert page.isVisible(), name
    win.close()


def test_chart_tooltip_empty_does_not_crash():
    app = _app()
    apply_theme(app, "dark")
    chart = SurplusChart()
    chart.show()
    app.processEvents()
    chart._tip_index = -1
    chart._show_cursor_tip()
    chart._hovered(False, 0)
    chart.close()


def test_migrate_file_has_no_destructive_sql():
    text = Path(__file__).resolve().parents[1].joinpath("src/budgetwatch/db/migrate.py").read_text()
    upper = text.upper()
    assert "DROP TABLE" not in upper
    assert "DELETE FROM" not in upper
    assert "TRUNCATE" not in upper
    assert ACCENT == "#F97316"
