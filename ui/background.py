from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal


class FunctionThread(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], object]) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:  # noqa: D401, N802
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(result)


class ProgressThread(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    progress_changed = Signal(int, str, str)

    def __init__(self, fn: Callable[[Callable[[int, str, str], None]], object]) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:  # noqa: D401, N802
        try:
            result = self._fn(self._emit_progress)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(result)

    def _emit_progress(self, percent: int, stage: str, detail: str = "") -> None:
        self.progress_changed.emit(percent, stage, detail)
