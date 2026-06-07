from __future__ import annotations

from collections.abc import Callable
from inspect import signature
from typing import TypeVar

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


T = TypeVar("T")


class WorkerSignals(QObject):
    progress = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()


class FunctionWorker(QRunnable):
    def __init__(self, function: Callable[[], T]) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.function = function
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            if len(signature(self.function).parameters) == 1:
                result = self.function(self._emit_progress)
            else:
                result = self.function()
        except Exception as exc:
            self._emit_failed(str(exc))
        else:
            self._emit_succeeded(result)
        finally:
            self._emit_finished()

    def _emit_progress(self, payload: object) -> None:
        try:
            self.signals.progress.emit(payload)
        except RuntimeError:
            pass

    def _emit_succeeded(self, payload: object) -> None:
        try:
            self.signals.succeeded.emit(payload)
        except RuntimeError:
            pass

    def _emit_failed(self, message: str) -> None:
        try:
            self.signals.failed.emit(message)
        except RuntimeError:
            pass

    def _emit_finished(self) -> None:
        try:
            self.signals.finished.emit()
        except RuntimeError:
            pass
