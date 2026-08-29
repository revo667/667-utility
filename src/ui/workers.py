from __future__ import annotations

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QWidget


DEFAULT_TIMEOUT_MS = 15_000


def stop_worker(worker: QThread | None, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> bool:
    if worker is None:
        return True

    try:
        if not worker.isRunning():
            return True
    except RuntimeError:
        return True


    worker.requestInterruption()
    worker.quit()

    if worker.wait(timeout_ms):
        return True

    worker.terminate()
    return worker.wait(2000)


def stop_all_threads(root: QWidget, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> int:
    stopped = 0
    for worker in root.findChildren(QThread):
        if stop_worker(worker, timeout_ms):
            stopped += 1
    return stopped
