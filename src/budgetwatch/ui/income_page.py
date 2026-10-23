from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.models.entities import PaySource, Paycheck
from budgetwatch.services.budget import BudgetService, ValidationError
from budgetwatch.services.income import income_labels
from budgetwatch.services.payday import needs_anchor
from budgetwatch.ui.dialogs import PaycheckDialog, PaySourceDialog
from budgetwatch.ui.formatters import format_date, format_money
from budgetwatch.ui.layout import money_item, page_margins, style_table, text_item
from budgetwatch.ui.widgets import (
    MoneyEdit,
    WarningBanner,
    confirm_delete,
    date_from_edit,
    make_date_edit,
    show_error,
)

JOB_COL_MIN = 380
JOB_COL_MAX = 420
FIELD_MIN = 220
HSPLITTER_PREF = "income_hsplitter"


class IncomePage(QWidget):
    def __init__(self, service: BudgetService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self._selected_source_id: int | None = None
        self._loading = False
        self._unlinked = False
        self._link_date: date | None = None
        self._refocus_amount = False
        self._splitter_ready = False

        layout = QVBoxLayout(self)
        page_margins(layout)

        title = QLabel("Income")
        title.setObjectName("pageTitle")
        helper = QLabel("Log deposits and check each job's typical pay.")
        helper.setObjectName("helperText")
        helper.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(helper)

        self.banner = WarningBanner()
        layout.addWidget(self.banner)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("incomeSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(2)
        self.splitter.addWidget(self._build_left_column())
        self.splitter.addWidget(self._build_checks_panel())
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.splitterMoved.connect(self._save_splitter)
        layout.addWidget(self.splitter, 1)

        self.pay_source.currentIndexChanged.connect(self._on_form_changed)
        self.pay_date.dateChanged.connect(self._on_form_changed)

    def _build_left_column(self) -> QWidget:
        column = QWidget()
        column.setMinimumWidth(JOB_COL_MIN)
        column.setMaximumWidth(JOB_COL_MAX)
        column.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        col = QVBoxLayout(column)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)
        col.addWidget(self._build_jobs_group())
        col.addWidget(self._build_paycheck_form())
        col.addStretch(1)
        return column

    def _build_jobs_group(self) -> QWidget:
        box = QGroupBox("Jobs")
        box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(box)
        layout.setSpacing(8)
        self.jobs = QListWidget()
        self.jobs.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
        )
        self.jobs.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.jobs.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.jobs.setSpacing(0)
        self.jobs.itemSelectionChanged.connect(self._on_job_selected)
        layout.addWidget(self.jobs)
        self.job_detail = QLabel("Select a job.")
        self.job_detail.setObjectName("helperText")
        self.job_detail.setWordWrap(True)
        layout.addWidget(self.job_detail)
        buttons = QHBoxLayout()
        add_job = QPushButton("Add job")
        add_job.clicked.connect(self._add_job)
        edit_job = QPushButton("Edit job")
        edit_job.clicked.connect(self._edit_job)
        buttons.addWidget(add_job)
        buttons.addWidget(edit_job)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return box

    def _build_paycheck_form(self) -> QWidget:
        box = QGroupBox("Log a paycheck")
        box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        grid = QGridLayout(box)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setColumnMinimumWidth(0, 120)
        grid.setColumnMinimumWidth(1, FIELD_MIN)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(99, 0)

        def label(text: str) -> QLabel:
            widget = QLabel(text)
            widget.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            widget.setWordWrap(False)
            return widget

        self.pay_source = QComboBox()
        self.pay_source.setMinimumWidth(FIELD_MIN)
        self.pay_date = make_date_edit(date.today())
        self.pay_date.setMinimumWidth(FIELD_MIN)
        self.pay_amount = MoneyEdit()
        self.pay_amount.setPlaceholderText("Net amount")
        self.pay_amount.setMinimumWidth(FIELD_MIN)
        self.pay_amount.clear()
        self.pay_include = QCheckBox("Count this toward typical pay?")
        self.pay_include.setChecked(True)
        self.pay_notes = QLineEdit()
        self.pay_notes.setPlaceholderText("Overtime, bonus, short week...")
        self.pay_notes.setMinimumWidth(FIELD_MIN)
        self.pay_link = QLabel("Not linked")
        self.pay_link.setObjectName("helperText")
        self.pay_link.setWordWrap(True)
        self.pay_link.setMinimumWidth(FIELD_MIN)
        self.unlink_btn = QPushButton("Unlink payday")
        self.unlink_btn.clicked.connect(self._unlink)
        self.unlink_btn.setVisible(False)
        save = QPushButton("Save paycheck")
        save.setObjectName("primary")
        save.clicked.connect(self.save_paycheck)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._clear_form)
        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addWidget(save)
        actions_layout.addWidget(clear)
        actions_layout.addStretch(1)

        rows = [
            ("Which job?", self.pay_source),
            ("Pay date", self.pay_date),
            ("Net amount", self.pay_amount),
            ("Count toward typical", self.pay_include),
            ("Notes", self.pay_notes),
            ("Linked payday", self.pay_link),
        ]
        for row, (text, field) in enumerate(rows):
            grid.addWidget(label(text), row, 0)
            grid.addWidget(field, row, 1)
        self._unlink_row = 6
        grid.addWidget(self.unlink_btn, self._unlink_row, 1)
        grid.addWidget(actions, self._unlink_row + 1, 1)
        self._paycheck_form = box
        return box

    def _build_checks_panel(self) -> QWidget:
        box = QGroupBox("Paychecks")
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(box)
        self.checks = QTableWidget(0, 6)
        self.checks.setHorizontalHeaderLabels(
            [
                "Date",
                "Job",
                "Amount",
                "Counts toward typical",
                "Linked payday",
                "Notes",
            ]
        )
        style_table(self.checks)
        self.checks.verticalHeader().setDefaultSectionSize(32)
        header = self.checks.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.checks.doubleClicked.connect(self._edit_paycheck)
        layout.addWidget(self.checks, 1)
        buttons = QHBoxLayout()
        edit = QPushButton("Edit")
        edit.clicked.connect(self._edit_paycheck)
        delete = QPushButton("Delete")
        delete.setObjectName("danger")
        delete.clicked.connect(self._delete_paycheck)
        buttons.addWidget(edit)
        buttons.addWidget(delete)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return box

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._splitter_ready:
            self._restore_splitter()
            self._splitter_ready = True
        self._fit_jobs_list()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._save_splitter()
        super().hideEvent(event)

    def _restore_splitter(self) -> None:
        raw = self.service.get_pref(HSPLITTER_PREF)
        if raw and "," in raw:
            left, right = raw.split(",", 1)
            try:
                self.splitter.setSizes(
                    [max(JOB_COL_MIN, int(left)), max(400, int(right))]
                )
                return
            except ValueError:
                pass
        self.splitter.setSizes([400, 700])

    def _save_splitter(self) -> None:
        sizes = self.splitter.sizes()
        if len(sizes) != 2:
            return
        try:
            self.service.set_pref(HSPLITTER_PREF, f"{sizes[0]},{sizes[1]}")
        except Exception:
            return

    def _fit_jobs_list(self) -> None:
        count = self.jobs.count()
        if count == 0:
            self.jobs.setFixedHeight(32)
            return
        row_h = self.jobs.sizeHintForRow(0)
        if row_h < 22:
            row_h = self.jobs.fontMetrics().height() + 12
        frame = self.jobs.frameWidth() * 2
        extra = self.jobs.spacing() * max(count - 1, 0)
        self.jobs.setFixedHeight(count * row_h + extra + frame + 8)

    def refresh(self) -> None:
        self._loading = True
        sources = self.service.list_sources()
        labels = income_labels(sources)
        selected = self._selected_source_id
        current_job = self.pay_source.currentData()
        self.jobs.blockSignals(True)
        self.jobs.clear()
        keep_row = 0
        for row, source in enumerate(sources):
            if source.id is None:
                continue
            item = QListWidgetItem(labels.get(source.id, f"Income {row + 1}"))
            item.setData(Qt.ItemDataRole.UserRole, source.id)
            self.jobs.addItem(item)
            if source.id == selected:
                keep_row = row
        if sources:
            self.jobs.setCurrentRow(keep_row)
        self.jobs.blockSignals(False)
        self._fit_jobs_list()

        self.pay_source.blockSignals(True)
        self.pay_source.clear()
        for source in sources:
            if source.id is None:
                continue
            label = labels.get(source.id, "Income")
            self.pay_source.addItem(label, source.id)
            if current_job is not None and source.id == current_job:
                self.pay_source.setCurrentIndex(self.pay_source.count() - 1)
            elif selected is not None and source.id == selected and current_job is None:
                self.pay_source.setCurrentIndex(self.pay_source.count() - 1)
        self.pay_source.blockSignals(False)

        warnings = []
        for source in sources:
            if needs_anchor(source):
                warnings.append(
                    "Set a recent payday before upcoming pay can be predicted"
                )
                break
        self.banner.set_messages(warnings)
        self._loading = False
        self._on_job_selected()
        self._refresh_link_hint()
        if self._refocus_amount:
            self._refocus_amount = False
            self.pay_amount.setFocus()
            self.pay_amount.selectAll()

    def _current_job(self) -> PaySource | None:
        item = self.jobs.currentItem()
        if item is None:
            return None
        source_id = item.data(Qt.ItemDataRole.UserRole)
        if source_id is None:
            return None
        return self.service.get_source(int(source_id))

    def _on_job_selected(self) -> None:
        source = self._current_job()
        self._selected_source_id = source.id if source else None
        if source is not None and source.id is not None:
            idx = self.pay_source.findData(source.id)
            if idx >= 0:
                self.pay_source.blockSignals(True)
                self.pay_source.setCurrentIndex(idx)
                self.pay_source.blockSignals(False)
                if not self._loading:
                    self._refresh_link_hint()
        self._update_job_detail(source)
        self._fill_checks()

    def _update_job_detail(self, source: PaySource | None) -> None:
        if source is None:
            self.job_detail.setText("Select a job.")
            return
        stats = self.service.source_stats(source)
        symbol = self.service.get_settings().currency_symbol
        lines = [source.frequency.value]
        if stats["needs_anchor"]:
            lines.append("Set a recent payday before upcoming pay can be predicted.")
        paydays = stats["next_paydays"]
        if paydays:
            lines.append(f"Next payday: {format_date(paydays[0])}")
        if source.amount_override is not None:
            lines.append(f"Override: {format_money(source.amount_override, symbol)}")
        elif stats["average"] is None:
            lines.append("Average: not enough data (need 2 checks).")
        else:
            lines.append(f"Average: {format_money(stats['average'], symbol)}")
        lines.append(f"Included checks in window: {stats['check_count']}")
        self.job_detail.setText("\n".join(lines))

    def _fill_checks(self) -> None:
        symbol = self.service.get_settings().currency_symbol
        source_list = self.service.list_sources()
        sources = {s.id: s for s in source_list}
        labels = income_labels(source_list)
        selected_job = self._selected_source_id
        checks = self.service.list_paychecks()
        if selected_job is not None:
            checks = [c for c in checks if c.source_id == selected_job]
        keep_id = self._selected_paycheck_id()
        self.checks.blockSignals(True)
        self.checks.setRowCount(len(checks))
        keep_row = -1
        for row, paycheck in enumerate(checks):
            source = sources.get(paycheck.source_id)
            linked = (
                format_date(paycheck.occurrence_date)
                if paycheck.occurrence_date
                else "Not linked"
            )
            self.checks.setItem(row, 0, text_item(paycheck.date.isoformat()))
            self.checks.setItem(
                row,
                1,
                text_item(
                    labels.get(paycheck.source_id, source.name if source else "?")
                ),
            )
            self.checks.setItem(row, 2, money_item(format_money(paycheck.amount, symbol)))
            self.checks.setItem(
                row, 3, text_item("Yes" if paycheck.include_in_average else "No")
            )
            self.checks.setItem(row, 4, text_item(linked))
            self.checks.setItem(row, 5, text_item(paycheck.notes))
            for col in range(6):
                self.checks.item(row, col).setData(Qt.ItemDataRole.UserRole, paycheck.id)
            if paycheck.id == keep_id:
                keep_row = row
        if keep_row >= 0:
            self.checks.selectRow(keep_row)
        else:
            self.checks.clearSelection()
        self.checks.blockSignals(False)

    def _on_form_changed(self) -> None:
        if self._loading:
            return
        self._refresh_link_hint()

    def _refresh_link_hint(self) -> None:
        if self._unlinked:
            self._link_date = None
            self.pay_link.setText("Not linked")
            self.unlink_btn.setVisible(False)
            return
        source_id = self.pay_source.currentData()
        if source_id is None:
            self._link_date = None
            self.pay_link.setText("Not linked")
            self.unlink_btn.setVisible(False)
            return
        suggested = self.service.suggest_link(
            int(source_id), date_from_edit(self.pay_date)
        )
        self._link_date = suggested
        if suggested:
            self.pay_link.setText(f"Linked to scheduled payday {format_date(suggested)}")
            self.unlink_btn.setVisible(True)
        else:
            self.pay_link.setText("Not linked")
            self.unlink_btn.setVisible(False)

    def save_paycheck(self) -> None:
        source_id = self.pay_source.currentData()
        amount = self.pay_amount.amount()
        if source_id is None:
            show_error(self, "Choose a pay source.")
            return
        if amount is None:
            show_error(self, "Enter an amount greater than 0")
            return
        saved_date = date_from_edit(self.pay_date)
        try:
            self.service.create_paycheck(
                Paycheck(
                    source_id=int(source_id),
                    date=saved_date,
                    amount=amount,
                    notes=self.pay_notes.text().strip(),
                    include_in_average=self.pay_include.isChecked(),
                    occurrence_date=None if self._unlinked else self._link_date,
                ),
                auto_link=not self._unlinked,
            )
        except ValidationError as exc:
            show_error(self, str(exc))
            return
        self.pay_amount.clear()
        self.pay_notes.clear()
        self._unlinked = False
        self._advance_date_after_save(int(source_id), saved_date)
        self._refocus_amount = True
        self.pay_amount.setFocus()

    def _advance_date_after_save(self, source_id: int, saved_date: date) -> None:
        source = self.service.get_source(source_id)
        if source is None:
            return
        stats = self.service.source_stats(source)
        upcoming = [d for d in stats["next_paydays"] if d > saved_date]
        if not upcoming:
            upcoming = stats["next_paydays"]
        if upcoming:
            self.pay_date.setDate(upcoming[0])

    def _clear_form(self) -> None:
        self.pay_amount.clear()
        self.pay_notes.clear()
        self.pay_include.setChecked(True)
        self._unlinked = False
        self._refresh_link_hint()
        self.pay_amount.setFocus()

    def _unlink(self) -> None:
        self._unlinked = True
        self._refresh_link_hint()

    def _add_job(self) -> None:
        dialog = PaySourceDialog(self.service, self)
        dialog.setWindowTitle("Add job")
        dialog.exec()

    def _edit_job(self) -> None:
        source = self._current_job()
        if source is None:
            show_error(self, "Select a job to edit.")
            return
        dialog = PaySourceDialog(self.service, self, source=source)
        dialog.setWindowTitle("Edit job")
        dialog.exec()

    def _selected_paycheck_id(self) -> int | None:
        items = self.checks.selectedItems()
        if not items:
            return None
        value = items[0].data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    def _edit_paycheck(self) -> None:
        paycheck_id = self._selected_paycheck_id()
        if paycheck_id is None:
            return
        paycheck = self.service.get_paycheck(paycheck_id)
        if paycheck is None:
            return
        PaycheckDialog(self.service, self, paycheck=paycheck).exec()

    def _delete_paycheck(self) -> None:
        paycheck_id = self._selected_paycheck_id()
        if paycheck_id is None:
            return
        if not confirm_delete(self, "Delete paycheck", "Delete this paycheck?"):
            return
        self.service.delete_paycheck(paycheck_id)

    def new_item(self) -> None:
        self._clear_form()

    def focus_default(self) -> None:
        self.pay_amount.setFocus()
        self.pay_amount.selectAll()

    def save_focused(self) -> None:
        self.save_paycheck()
