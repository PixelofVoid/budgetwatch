from __future__ import annotations

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSet,
    QChart,
    QChartView,
    QStackedBarSeries,
    QValueAxis,
)
from PySide6.QtCore import QMargins, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.models.entities import MonthRollup
from budgetwatch.ui.formatters import format_money
from budgetwatch.ui import theme as t


class SurplusChart(QWidget):
    """6-month calendar leftover bars. Series objects are reused, not recreated."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._points: list[MonthRollup] = []
        self._symbol = "$"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.chart = QChart()
        self.chart.setBackgroundVisible(True)
        self.chart.setBackgroundBrush(QBrush(QColor(t.SURFACE)))
        self.chart.setPlotAreaBackgroundVisible(True)
        self.chart.setPlotAreaBackgroundBrush(QBrush(QColor(t.BG)))
        self.chart.setTitle("")
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        self.chart.legend().setLabelColor(QColor(t.MUTED))
        self.chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
        chart_layout = self.chart.layout()
        if chart_layout is not None:
            chart_layout.setContentsMargins(0, 0, 0, 0)
        self.chart.setMargins(QMargins(4, 4, 4, 4))

        self.surplus = QBarSet("Surplus")
        self.deficit = QBarSet("Deficit")
        self.surplus.setColor(QColor(t.GREEN))
        self.deficit.setColor(QColor(t.RED))
        self.surplus.setBorderColor(QColor(t.GREEN))
        self.deficit.setBorderColor(QColor(t.RED))
        for _ in range(6):
            self.surplus.append(0.0)
            self.deficit.append(0.0)

        self.series = QStackedBarSeries()
        self.series.setBarWidth(0.62)
        self.series.append(self.surplus)
        self.series.append(self.deficit)
        self.chart.addSeries(self.series)

        self.series.setLabelsVisible(False)

        self.axis_x = QBarCategoryAxis()
        self.axis_x.append(["", "", "", "", "", ""])
        self.axis_x.setLabelsColor(QColor(t.MUTED))
        self.axis_x.setGridLineVisible(False)
        self.axis_x.setLinePen(QPen(QColor(t.BORDER)))
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        self.series.attachAxis(self.axis_x)

        self.axis_y = QValueAxis()
        self.axis_y.setLabelFormat("%.0f")
        self.axis_y.setLabelsColor(QColor(t.MUTED))
        self.axis_y.setGridLineColor(QColor(t.BORDER))
        zero_pen = QPen(QColor(t.TEXT))
        zero_pen.setWidth(1)
        self.axis_y.setLinePen(zero_pen)
        self.axis_y.setTitleText("")
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        self.series.attachAxis(self.axis_y)

        self.view = QChartView(self.chart)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setMinimumHeight(260)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setBackgroundBrush(QBrush(QColor(t.SURFACE)))
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.view, 1)
        self._tip_timer = QTimer(self)
        self._tip_timer.setSingleShot(True)
        self._tip_timer.setInterval(280)
        self._tip_index = -1
        self._tip_timer.timeout.connect(self._show_cursor_tip)

        self.subtitle = QLabel("Green = money left that month. Red = short that month.")
        self.subtitle.setObjectName("chartSubtitle")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        self.detail = QLabel("Hover or click a bar for month details.")
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet(f"color: {t.MUTED};")
        layout.addWidget(self.detail)

        self.surplus.hovered.connect(self._hovered)
        self.deficit.hovered.connect(self._hovered)
        self.series.clicked.connect(self._clicked)

    def apply_palette(self) -> None:
        from budgetwatch.ui import theme as t

        self.chart.setBackgroundBrush(QBrush(QColor(t.SURFACE)))
        self.chart.setPlotAreaBackgroundBrush(QBrush(QColor(t.BG)))
        self.chart.legend().setLabelColor(QColor(t.MUTED))
        self.view.setBackgroundBrush(QBrush(QColor(t.SURFACE)))
        self.surplus.setColor(QColor(t.GREEN))
        self.deficit.setColor(QColor(t.RED))
        self.surplus.setBorderColor(QColor(t.GREEN))
        self.deficit.setBorderColor(QColor(t.RED))
        self.axis_x.setLabelsColor(QColor(t.MUTED))
        self.axis_x.setLinePen(QPen(QColor(t.BORDER)))
        self.axis_y.setLabelsColor(QColor(t.MUTED))
        self.axis_y.setGridLineColor(QColor(t.BORDER))
        self.axis_y.setLinePen(QPen(QColor(t.TEXT)))
        self.axis_y.setTitleBrush(QBrush(QColor(t.DIM)))
        self.detail.setStyleSheet(f"color: {t.MUTED};")

    def refresh(self, months: list[MonthRollup], symbol: str) -> None:
        self.apply_palette()
        self._points = months[:6]
        self._symbol = symbol
        categories: list[str] = []
        peak = 1.0
        for i in range(6):
            if i < len(self._points):
                point = self._points[i]
                leftover = float(point.leftover)
                label = point.label + ("*" if point.income_is_partial else "")
            else:
                leftover = 0.0
                label = ""
            categories.append(label)
            if leftover >= 0:
                self.surplus.replace(i, leftover)
                self.deficit.replace(i, 0.0)
            else:
                self.surplus.replace(i, 0.0)
                self.deficit.replace(i, leftover)
            peak = max(peak, abs(leftover))
        self.axis_x.clear()
        self.axis_x.append(categories)
        pad = peak * 1.18 if peak else 1.0
        self.axis_y.setRange(-pad, pad)
        self.axis_y.applyNiceNumbers()
        # Keep zero in range even after nice-number rounding.
        lower, upper = self.axis_y.min(), self.axis_y.max()
        bound = max(abs(lower), abs(upper), pad)
        self.axis_y.setRange(-bound, bound)
        if self._points:
            self._show_point(0)

    def _hovered(self, status: bool, index: int) -> None:
        if status:
            self._tip_index = index
            self._show_point(index)
            self._tip_timer.start()
        else:
            self._tip_timer.stop()
            self._tip_index = -1
            QToolTip.hideText()

    def _clicked(self, index: int, _barset: QBarSet) -> None:
        self._show_point(index)

    def _show_cursor_tip(self) -> None:
        if not self.isVisible() or self.view is None:
            return
        if not (0 <= self._tip_index < len(self._points)):
            return
        point = self._points[self._tip_index]
        short = f"{point.label}: leftover {format_money(point.leftover, self._symbol)}"
        pos = QCursor.pos()
        pos.setY(pos.y() - 32)
        try:
            QToolTip.showText(pos, short, self.view)
        except RuntimeError:
            return

    def _show_point(self, index: int, tooltip: bool = False) -> None:
        if not (0 <= index < len(self._points)):
            return
        point = self._points[index]
        symbol = self._symbol
        estimated = ""
        if point.income_is_partial:
            names = ", ".join(point.unknown_sources) or "a pay source"
            estimated = (
                f" Estimated — not enough data for {names}. "
                "Unknown paydays are omitted, not counted as $0."
            )
        text = (
            f"{point.label}: income {format_money(point.income, symbol)} · "
            f"bills {format_money(point.bills, symbol)} · "
            f"leftover {format_money(point.leftover, symbol)} · "
            f"after savings {format_money(point.leftover_after_savings, symbol)}."
            f"{estimated}"
        )
        self.detail.setText(text)
