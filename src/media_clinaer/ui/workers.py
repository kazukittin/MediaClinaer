from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


T = TypeVar("T")


class WorkerSignals(QObject):
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
            result = self.function()
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()
