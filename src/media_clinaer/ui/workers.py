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
        self.function = function
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            if len(signature(self.function).parameters) == 1:
                result = self.function(self.signals.progress.emit)
            else:
                result = self.function()
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()
