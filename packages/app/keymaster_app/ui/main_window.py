from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
                               QProgressBar, QPushButton, QSlider, QSplitter, QStackedWidget, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from keymaster_app import PACKAGE_DIR, clips, settings
from keymaster_app.batch import BATCH_FINISHED, Batch
from keymaster_app.commands import FORMATS, OUTPUT_KINDS, KeyOptions
from keymaster_app.i18n import current, t
from keymaster_app.media import HINT_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, collect_inputs, output_folder, preview_source
from keymaster_app.texts import error_text, status_text, summary_text
from keymaster_app.ui.preview import PreviewView, load_image
from keymaster_app.ui.setup_check import SetupCheckDialog

COL_CLIP, COL_HINT, COL_STATUS, COL_PROGRESS = range(4)
LANGUAGE_CODES = ("en", "es-419")


def _patterns(extensions: set[str]) -> str:
    return " ".join(f"*{ext}" for ext in sorted(extensions))


class _Bridge(QObject):
    batch_signal = Signal(str, object)


def _card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(10)
    return frame, layout


def _slider(value: int) -> tuple[QSlider, QHBoxLayout]:
    slider = QSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(value)
    readout = QLabel()
    readout.setText(f"{value / 100:.2f}")
    readout.setMinimumWidth(36)
    readout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    slider.valueChanged.connect(lambda v: readout.setText(f"{v / 100:.2f}"))
    row = QHBoxLayout()
    row.addWidget(slider, 1)
    row.addWidget(readout)
    return slider, row


def _section() -> QLabel:
    label = QLabel()
    label.setObjectName("section")
    return label


class MainWindow(QMainWindow):
    def __init__(self, env: dict[str, str] | None = None):
        super().__init__()
        self.env = env
        self.resolved = settings.resolve()
        self.queue = clips.ClipQueue()
        self.batch: Batch | None = None
        self.items: dict[int, QTreeWidgetItem] = {}
        self.bars: dict[int, QProgressBar] = {}
        self.notice: tuple[str, dict] | None = None
        self.setup_dialog: SetupCheckDialog | None = None
        self.bridge = _Bridge(self)
        self.bridge.batch_signal.connect(self._on_batch_signal)
        self.setAcceptDrops(True)
        self.resize(1180, 720)
        icon = PACKAGE_DIR / "assets" / "icon.svg"
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))
        self._build()
        self.retranslate()
        self._refresh_controls()

    def _build(self) -> None:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title_label = QLabel()
        self.title_label.setObjectName("title")
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("subtitle")
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)
        header.addLayout(titles)
        header.addStretch(1)
        self.setup_button = QPushButton()
        self.setup_button.clicked.connect(self.show_setup_check)
        self.language_label = QLabel()
        self.language_label.setObjectName("muted")
        self.language_combo = QComboBox()
        for code in LANGUAGE_CODES:
            self.language_combo.addItem(code, code)
        self.language_combo.setCurrentIndex(LANGUAGE_CODES.index(current().language))
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        header.addWidget(self.setup_button)
        header.addSpacing(12)
        header.addWidget(self.language_label)
        header.addWidget(self.language_combo)
        outer.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_queue())
        splitter.addWidget(self._build_side())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 1)

        footer = QHBoxLayout()
        footer.setSpacing(12)
        status_box = QVBoxLayout()
        self.status_label = QLabel()
        self.status_label.setObjectName("muted")
        self.overall_bar = QProgressBar()
        self.overall_bar.setRange(0, 1000)
        self.overall_bar.setTextVisible(False)
        status_box.addWidget(self.status_label)
        status_box.addWidget(self.overall_bar)
        footer.addLayout(status_box, 1)
        self.cancel_button = QPushButton()
        self.cancel_button.setObjectName("danger")
        self.cancel_button.clicked.connect(self.cancel)
        self.start_button = QPushButton()
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.start)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.start_button)
        outer.addLayout(footer)
        self.setCentralWidget(root)

    def _build_queue(self) -> QWidget:
        frame, layout = _card()
        top = QHBoxLayout()
        self.queue_section = _section()
        self.add_files_button = QPushButton()
        self.add_files_button.clicked.connect(self.browse_files)
        self.add_folder_button = QPushButton()
        self.add_folder_button.clicked.connect(self.browse_folder)
        top.addWidget(self.queue_section)
        top.addStretch(1)
        top.addWidget(self.add_files_button)
        top.addWidget(self.add_folder_button)
        layout.addLayout(top)
        self.queue_stack = QStackedWidget()
        self.drop_hint = QLabel()
        self.drop_hint.setObjectName("dropHint")
        self.drop_hint.setAlignment(Qt.AlignCenter)
        self.drop_hint.setWordWrap(True)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_CLIP, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_HINT, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_PROGRESS, QHeaderView.Fixed)
        header.resizeSection(COL_PROGRESS, 120)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.queue_stack.addWidget(self.drop_hint)
        self.queue_stack.addWidget(self.tree)
        layout.addWidget(self.queue_stack, 1)

        row = QHBoxLayout()
        self.hint_button = QPushButton()
        self.hint_button.clicked.connect(self.browse_hint)
        self.clear_hint_button = QPushButton()
        self.clear_hint_button.clicked.connect(self.clear_hint)
        self.remove_button = QPushButton()
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_done_button = QPushButton()
        self.clear_done_button.clicked.connect(self.clear_finished)
        for button in (self.hint_button, self.clear_hint_button):
            row.addWidget(button)
        row.addStretch(1)
        row.addWidget(self.remove_button)
        row.addWidget(self.clear_done_button)
        layout.addLayout(row)
        return frame

    def _build_side(self) -> QWidget:
        side = QWidget()
        column = QVBoxLayout(side)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(14)

        frame, layout = _card()
        self.options_section = _section()
        layout.addWidget(self.options_section)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        self.quality_label = QLabel()
        self.quality_slider, quality_row = _slider(95)
        grid.addWidget(self.quality_label, 0, 0)
        grid.addLayout(quality_row, 0, 1)

        self.despill_label = QLabel()
        self.despill_slider, despill_row = _slider(50)
        grid.addWidget(self.despill_label, 1, 0)
        grid.addLayout(despill_row, 1, 1)

        self.outputs_label = QLabel()
        outputs_row = QGridLayout()
        self.output_checks: dict[str, QCheckBox] = {}
        outputs_row.setVerticalSpacing(6)
        for index, kind in enumerate(OUTPUT_KINDS):
            box = QCheckBox()
            box.setChecked(kind != "checker")
            self.output_checks[kind] = box
            outputs_row.addWidget(box, index // 2, index % 2)
        grid.addWidget(self.outputs_label, 2, 0, Qt.AlignTop)
        grid.addLayout(outputs_row, 2, 1)

        self.format_label = QLabel()
        self.format_combo = QComboBox()
        for code in FORMATS:
            self.format_combo.addItem(code, code)
        grid.addWidget(self.format_label, 3, 0)
        grid.addWidget(self.format_combo, 3, 1)

        self.low_vram_check = QCheckBox()
        grid.addWidget(self.low_vram_check, 4, 1)

        self.folder_label = QLabel()
        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setClearButtonEnabled(True)
        self.folder_button = QPushButton()
        self.folder_button.clicked.connect(self.browse_output_folder)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.folder_button)
        grid.addWidget(self.folder_label, 5, 0)
        grid.addLayout(folder_row, 5, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        column.addWidget(frame)

        preview_frame, preview_layout = _card()
        self.preview_section = _section()
        self.preview_name = QLabel()
        self.preview_name.setObjectName("muted")
        self.preview = PreviewView()
        self.open_folder_button = QPushButton()
        self.open_folder_button.clicked.connect(self.open_output_folder)
        preview_layout.addWidget(self.preview_section)
        preview_layout.addWidget(self.preview_name)
        preview_layout.addWidget(self.preview, 1)
        preview_layout.addWidget(self.open_folder_button, 0, Qt.AlignRight)
        column.addWidget(preview_frame, 1)
        self.option_widgets = [self.quality_slider, self.despill_slider, self.format_combo, self.low_vram_check,
                               self.folder_edit, self.folder_button, *self.output_checks.values()]
        return side

    def retranslate(self) -> None:
        self.setWindowTitle(t("app.window_title"))
        self.title_label.setText(t("app.title"))
        self.subtitle_label.setText(t("app.subtitle"))
        self.setup_button.setText(t("app.setup.open"))
        self.language_label.setText(t("app.language.label"))
        self.language_combo.setItemText(0, t("app.language.en"))
        self.language_combo.setItemText(1, t("app.language.es_419"))
        self.queue_section.setText(t("app.queue.section"))
        self.drop_hint.setText(t("app.queue.drop_hint"))
        self.tree.setHeaderLabels([t("app.queue.col_clip"), t("app.queue.col_hint"),
                                   t("app.queue.col_status"), t("app.queue.col_progress")])
        self.add_files_button.setText(t("app.queue.add_files"))
        self.add_folder_button.setText(t("app.queue.add_folder"))
        self.hint_button.setText(t("app.queue.set_hint"))
        self.hint_button.setToolTip(t("app.queue.set_hint_tip"))
        self.clear_hint_button.setText(t("app.queue.clear_hint"))
        self.remove_button.setText(t("app.queue.remove"))
        self.clear_done_button.setText(t("app.queue.clear_done"))
        self.options_section.setText(t("app.options.section"))
        self.quality_label.setText(t("app.options.hint_quality"))
        self.quality_slider.setToolTip(t("app.options.hint_quality_tip"))
        self.despill_label.setText(t("app.options.despill"))
        self.despill_slider.setToolTip(t("app.options.despill_tip"))
        self.outputs_label.setText(t("app.options.outputs"))
        names = {"alpha": t("app.output.alpha"), "fg": t("app.output.fg"),
                 "cutout": t("app.output.cutout"), "checker": t("app.output.checker")}
        tips = {"alpha": t("app.output.alpha_tip"), "fg": t("app.output.fg_tip"),
                "cutout": t("app.output.cutout_tip"), "checker": t("app.output.checker_tip")}
        for kind, box in self.output_checks.items():
            box.setText(names[kind])
            box.setToolTip(tips[kind])
        self.format_label.setText(t("app.options.format"))
        self.format_combo.setItemText(0, t("app.format.exr"))
        self.format_combo.setItemText(1, t("app.format.video"))
        self.low_vram_check.setText(t("app.options.low_vram"))
        self.low_vram_check.setToolTip(t("app.options.low_vram_tip"))
        self.folder_label.setText(t("app.options.output_folder"))
        self.folder_edit.setPlaceholderText(t("app.options.output_folder_default"))
        self.folder_button.setText(t("app.options.browse"))
        self.preview_section.setText(t("app.preview.section"))
        self.open_folder_button.setText(t("app.preview.open_folder"))
        self.cancel_button.setText(t("app.cancel"))
        self.start_button.setText(t("app.start"))
        for clip in list(self.queue.clips):
            self._update_row(clip.id)
        self._update_preview()
        self._update_status()
        if self.setup_dialog:
            self.setup_dialog.retranslate()

    def _on_language_changed(self, index: int) -> None:
        code = self.language_combo.itemData(index)
        language = current().set_language(code)
        try:
            settings.save_language(language)
        except OSError:
            self.notice = ("save_failed", {})
        self.retranslate()

    def set_language(self, code: str) -> None:
        self.language_combo.setCurrentIndex(LANGUAGE_CODES.index(settings.normalize_language(code)))

    def options(self) -> KeyOptions:
        folder = self.folder_edit.text().strip()
        return KeyOptions(
            hint_quality=self.quality_slider.value() / 100,
            despill=self.despill_slider.value() / 100,
            outputs=tuple(k for k, box in self.output_checks.items() if box.isChecked()),
            format=self.format_combo.currentData(),
            output_root=folder or None,
            low_vram=self.low_vram_check.isChecked(),
        )

    def add_paths(self, paths: list[str]) -> list[clips.Clip]:
        found, skipped = collect_inputs(paths)
        added = self.queue.add(found)
        for clip in added:
            item = QTreeWidgetItem()
            item.setData(COL_CLIP, Qt.UserRole, clip.id)
            self.tree.addTopLevelItem(item)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setTextVisible(False)
            bar.setMaximumHeight(14)
            self.tree.setItemWidget(item, COL_PROGRESS, bar)
            self.items[clip.id] = item
            self.bars[clip.id] = bar
            self._update_row(clip.id)
        if skipped:
            self.notice = ("skipped", {"count": len(skipped)})
        elif added:
            self.notice = None
        if added and not self.tree.selectedItems():
            self.items[added[0].id].setSelected(True)
        self._refresh_controls()
        return added

    def selected_ids(self) -> list[int]:
        return [item.data(COL_CLIP, Qt.UserRole) for item in self.tree.selectedItems()]

    def select_clip(self, clip_id: int) -> None:
        self.tree.clearSelection()
        if clip_id in self.items:
            self.items[clip_id].setSelected(True)

    def _update_row(self, clip_id: int) -> None:
        clip = self.queue.get(clip_id)
        item = self.items.get(clip_id)
        if not clip or not item:
            return
        item.setText(COL_CLIP, clip.name)
        item.setToolTip(COL_CLIP, clip.path)
        item.setText(COL_HINT, Path(clip.hint).name if clip.hint else t("app.queue.no_hint"))
        item.setToolTip(COL_HINT, clip.hint or "")
        item.setText(COL_STATUS, status_text(clip))
        detail = (clip.error or {}).get("detail", "") if clip.status == clips.FAILED else ""
        item.setToolTip(COL_STATUS, detail)
        bar = self.bars.get(clip_id)
        if bar:
            bar.setValue(int(round(clip.progress * 1000)))

    def _refresh_controls(self) -> None:
        running = self.batch is not None and self.batch.running
        has_clips = len(self.queue) > 0
        self.queue_stack.setCurrentIndex(1 if has_clips else 0)
        selected = [self.queue.get(i) for i in self.selected_ids()]
        editable = [c for c in selected if c and c.status != clips.RUNNING]
        self.start_button.setEnabled(not running and has_clips)
        self.cancel_button.setEnabled(running)
        self.hint_button.setEnabled(len(editable) == 1)
        self.clear_hint_button.setEnabled(any(c.hint for c in editable))
        self.remove_button.setEnabled(bool(editable))
        self.clear_done_button.setEnabled(any(c.status == clips.DONE for c in self.queue.clips))
        for widget in self.option_widgets:
            widget.setEnabled(not running)
        self._update_status()

    def _update_status(self) -> None:
        self.overall_bar.setValue(int(round(self.queue.overall() * 1000)))
        running = self.batch is not None and self.batch.running
        if self.notice:
            kind, params = self.notice
            messages = {
                "skipped": lambda: t("app.notice.skipped", **params),
                "no_outputs": lambda: t("app.notice.no_outputs"),
                "empty": lambda: t("app.notice.empty"),
                "save_failed": lambda: t("app.notice.save_failed"),
                "cancelled": lambda: t("app.notice.cancelled"),
                "no_folder": lambda: t("app.notice.no_folder"),
            }
            self.status_label.setText(messages[kind]())
        elif running:
            self.status_label.setText(t("app.status.running_summary", done=self.queue.counts()[clips.DONE], total=len(self.queue)))
        elif len(self.queue):
            self.status_label.setText(summary_text(self.queue))
        else:
            self.status_label.setText(t("app.status.idle"))

    def _on_selection_changed(self) -> None:
        self._refresh_controls()
        self._update_preview()

    def _preview_clip(self) -> clips.Clip | None:
        ids = self.selected_ids()
        return self.queue.get(ids[0]) if ids else None

    def _update_preview(self) -> None:
        clip = self._preview_clip()
        self.preview_name.setText(clip.name if clip else "")
        self.open_folder_button.setEnabled(bool(clip and clip.status == clips.DONE))
        if not clip:
            self.preview.set_image(None)
            self.preview.set_message(t("app.preview.select"))
            return
        if clip.status != clips.DONE:
            self.preview.set_image(None)
            if clip.status == clips.FAILED:
                self.preview.set_message(error_text(clip.error))
            elif clip.status == clips.RUNNING:
                self.preview.set_message(t("app.preview.running"))
            else:
                self.preview.set_message(t("app.preview.not_yet"))
            return
        image = load_image(preview_source(clip.outputs))
        self.preview.set_image(image)
        self.preview.set_message("" if image else t("app.preview.unavailable"))

    def preview_loaded(self) -> bool:
        return self.preview.has_image()

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.add_paths(paths)
            event.acceptProposedAction()

    def browse_files(self) -> None:
        media = _patterns(VIDEO_EXTENSIONS | IMAGE_EXTENSIONS)
        files, _ = QFileDialog.getOpenFileNames(self, t("app.dialog.add_files"), "",
                                                t("app.dialog.media_filter", patterns=media))
        if files:
            self.add_paths(files)

    def browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, t("app.dialog.add_folder"))
        if folder:
            self.add_paths([folder])

    def browse_hint(self) -> None:
        ids = self.selected_ids()
        if len(ids) != 1:
            return
        clip = self.queue.get(ids[0])
        start = str(Path(clip.path).parent) if clip else ""
        path, _ = QFileDialog.getOpenFileName(self, t("app.dialog.hint"), start,
                                              t("app.dialog.image_filter", patterns=_patterns(HINT_EXTENSIONS)))
        if path:
            self.set_hint(ids[0], path)

    def set_hint(self, clip_id: int, path: str | None) -> None:
        if self.queue.set_hint(clip_id, path):
            self._update_row(clip_id)
            self._refresh_controls()

    def clear_hint(self) -> None:
        for clip_id in self.selected_ids():
            self.set_hint(clip_id, None)

    def browse_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, t("app.dialog.output_folder"), self.folder_edit.text())
        if folder:
            self.folder_edit.setText(folder)

    def _drop_rows(self, ids: list[int]) -> None:
        for clip_id in ids:
            item = self.items.pop(clip_id, None)
            self.bars.pop(clip_id, None)
            if item:
                self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        self._refresh_controls()
        self._update_preview()

    def remove_selected(self) -> None:
        self._drop_rows(self.queue.remove(self.selected_ids()))

    def clear_finished(self) -> None:
        self._drop_rows(self.queue.clear_finished())

    def open_output_folder(self) -> None:
        clip = self._preview_clip()
        if not clip:
            return
        folder = output_folder(clip.outputs, clip.output_dir)
        if folder and os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            self.notice = ("no_folder", {})
            self._update_status()

    def show_setup_check(self) -> None:
        if self.setup_dialog is None:
            self.setup_dialog = SetupCheckDialog(self._resolve, self)
        self.setup_dialog.show()
        self.setup_dialog.raise_()
        self.setup_dialog.run_check()

    def _resolve(self) -> settings.Resolved:
        self.resolved = settings.resolve()
        if current().core_dir != self.resolved.core:
            current().core_dir = self.resolved.core
            current().set_language(current().language)
        return self.resolved

    def start(self) -> bool:
        if self.batch is not None and self.batch.running:
            return False
        if not len(self.queue):
            self.notice = ("empty", {})
            self._update_status()
            return False
        options = self.options()
        if options.validate():
            self.notice = ("no_outputs", {})
            self._update_status()
            return False
        resolved = self._resolve()
        if settings.core_problem(resolved):
            self.show_setup_check()
            return False
        self.notice = None
        self.batch = Batch(self.queue, options, resolved.python, resolved.core,
                           notify=lambda kind, clip_id: self.bridge.batch_signal.emit(kind, clip_id), env=self.env)
        self.batch.start()
        for clip in self.queue.clips:
            self._update_row(clip.id)
        self._refresh_controls()
        return True

    def cancel(self) -> None:
        if self.batch is not None and self.batch.running:
            self.batch.cancel()
            self.cancel_button.setEnabled(False)

    def is_running(self) -> bool:
        return self.batch is not None and self.batch.running

    def _on_batch_signal(self, kind: str, clip_id: object) -> None:
        if kind == BATCH_FINISHED:
            if self.batch is not None:
                self.batch.join(5)
                if self.batch.cancelled:
                    self.notice = ("cancelled", {})
            self._refresh_controls()
            self._update_preview()
            return
        if isinstance(clip_id, int):
            self._update_row(clip_id)
            selected = self._preview_clip()
            if selected and selected.id == clip_id:
                self._update_preview()
        self._refresh_controls()

    def closeEvent(self, event) -> None:
        if self.batch is not None and self.batch.running:
            self.batch.cancel()
            self.batch.join(10)
        super().closeEvent(event)
