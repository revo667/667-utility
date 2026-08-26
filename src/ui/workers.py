"""Arka plan thread'lerini guvenle durdurma.

Neden gerekli: Qt, calisan bir QThread'in nesnesi yok edilirse sureci
abort eder ("QThread: Destroyed while thread is still running", SIGABRT).
Bu; uygulama kapanirken, sayfa yok edilirken veya ayni degiskene yeni bir
worker atanirken olur.

Iki kural:
  1. Her worker bir parent ile olusturulmali - boylece Qt onu bulabilir
     ve asagidaki sweep calisir.
  2. Kapanistan once stop_all_threads() cagrilmali.
"""

from __future__ import annotations

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QWidget

#: Uzun surebilecek isler var (brew install, tmutil thin). Cok kisa bir
#: timeout onlari terminate() ile kesip veri butunlugunu riske atar.
DEFAULT_TIMEOUT_MS = 15_000


def stop_worker(worker: QThread | None, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> bool:
    """Tek bir thread'i durdurur. Durduysa (veya zaten duruyorsa) True."""
    if worker is None:
        return True

    try:
        if not worker.isRunning():
            return True
    except RuntimeError:
        # C++ nesnesi zaten silinmis - yapacak bir sey yok.
        return True

    # requestInterruption: run() dongusu isInterruptionRequested() kontrol
    # ediyorsa erken cikar. quit(): event dongusu olan thread'ler icin.
    worker.requestInterruption()
    worker.quit()

    if worker.wait(timeout_ms):
        return True

    # Son care. Veri yazan bir is ortasindaysa bu iyi degil, ama sureci
    # abort ettirmekten iyidir.
    worker.terminate()
    return worker.wait(2000)


def stop_all_threads(root: QWidget, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> int:
    """root ve altindaki tum QThread'leri durdurur, durdurulan sayisini doner."""
    stopped = 0
    for worker in root.findChildren(QThread):
        if stop_worker(worker, timeout_ms):
            stopped += 1
    return stopped
