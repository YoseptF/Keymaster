from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from keymaster_app import settings
from keymaster_app.batch import run_doctor
from keymaster_app.i18n import t
from keymaster_app.runner import RunResult
from keymaster_app.texts import check_text, core_text


class _Bridge(QObject):
    finished = Signal(object)


class SetupCheckDialog(QDialog):
    def __init__(self, resolved_getter, parent: QWidget | None = None):
        super().__init__(parent)
        self.resolved_getter = resolved_getter
        self.bridge = _Bridge(self)
        self.bridge.finished.connect(self._on_finished)
        self.result: RunResult | None = None
        self.problem: str | None = None
        self.running = False
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        self.heading = QLabel()
        self.heading.setObjectName("title")
        self.intro = QLabel()
        self.intro.setObjectName("subtitle")
        self.intro.setWordWrap(True)
        layout.addWidget(self.heading)
        layout.addWidget(self.intro)

        paths = QFrame()
        paths.setObjectName("card")
        grid = QGridLayout(paths)
        self.python_label = QLabel()
        self.python_label.setObjectName("muted")
        self.python_value = QLabel()
        self.core_label = QLabel()
        self.core_label.setObjectName("muted")
        self.core_value = QLabel()
        for value in (self.python_value, self.core_value):
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value.setWordWrap(True)
        grid.addWidget(self.python_label, 0, 0)
        grid.addWidget(self.python_value, 0, 1)
        grid.addWidget(self.core_label, 1, 0)
        grid.addWidget(self.core_value, 1, 1)
        grid.setColumnStretch(1, 1)
        layout.addWidget(paths)

        self.checks_card = QFrame()
        self.checks_card.setObjectName("card")
        self.checks_layout = QGridLayout(self.checks_card)
        self.checks_layout.setColumnStretch(1, 1)
        layout.addWidget(self.checks_card)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.run_button = QPushButton()
        self.run_button.clicked.connect(self.run_check)
        self.close_button = QPushButton()
        self.close_button.setObjectName("primary")
        self.close_button.clicked.connect(self.accept)
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(t("app.setup.window_title"))
        self.heading.setText(t("app.setup.heading"))
        self.intro.setText(t("app.setup.intro"))
        self.python_label.setText(t("app.setup.python"))
        self.core_label.setText(t("app.setup.core"))
        self.run_button.setText(t("app.setup.run_again"))
        self.close_button.setText(t("app.setup.close"))
        self._render()

    def run_check(self) -> None:
        if self.running:
            return
        resolved = self.resolved_getter()
        self.python_value.setText(resolved.python)
        self.core_value.setText(resolved.core or t("app.setup.not_set"))
        self.problem = settings.core_problem(resolved)
        self.result = None
        if self.problem:
            self._render()
            return
        self.running = True
        self.run_button.setEnabled(False)
        self._render()
        threading.Thread(target=lambda: self.bridge.finished.emit(run_doctor(resolved.python, resolved.core)),
                         daemon=True).start()

    def _on_finished(self, result: RunResult) -> None:
        self.running = False
        self.run_button.setEnabled(True)
        self.result = result
        self._render()

    def _clear_checks(self) -> None:
        while self.checks_layout.count():
            item = self.checks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render(self) -> None:
        self._clear_checks()
        self.checks_card.setVisible(False)
        if self.problem == "core":
            self.status.setText(t("app.setup.core_missing"))
        elif self.problem == "python":
            self.status.setText(t("app.setup.python_missing"))
        elif self.running:
            self.status.setText(t("app.setup.running"))
        elif self.result is None:
            self.status.setText("")
        else:
            report = self.result.last("doctor")
            if report is None:
                error = self.result.last("error")
                detail = self.result.launch_error or (error or {}).get("detail") or self.result.stderr_tail.strip()
                message = core_text((error or {}).get("message_key", ""), (error or {}).get("params")) or t("app.setup.failed")
                self.status.setText(f"{message}\n{detail}".strip())
            else:
                checks = [c for c in report.get("checks", []) if isinstance(c, dict)]
                for row, check in enumerate(checks):
                    mark = QLabel("✓" if check.get("ok") else "✗")
                    mark.setObjectName("checkOk" if check.get("ok") else "checkBad")
                    message = QLabel(check_text(check))
                    message.setWordWrap(True)
                    self.checks_layout.addWidget(mark, row, 0)
                    self.checks_layout.addWidget(message, row, 1)
                self.checks_card.setVisible(bool(checks))
                self.status.setText(t("app.setup.all_ok") if report.get("ok") else t("app.setup.some_missing"))
        self.adjustSize()
