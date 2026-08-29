"""Surum bilgisi - tek kaynak.

APP_VERSION burada duruyor; pyproject.toml ve PyInstaller spec'i buradan
okuyor ki uc yerde ayri ayri guncellemek gerekmesin.

BUILD_SHA paketleme sirasinda CI tarafindan yazilir. Gece surumunde etiket
(nightly) sabit kaldigi icin surum numarasi degismez - hangi commit'ten
uretildigini yalnizca bu sha soyler. Gelistirme calismasinda bos kalir.
"""

from __future__ import annotations

APP_VERSION = "0.2.0"

#: CI paketleme oncesi bu satiri yeniden yazar (build.yml -> "Surum damgasi").
BUILD_SHA = ""


def short_sha(value: str | None = None) -> str:
    """Uzun sha'yi 7 haneye kisaltir. Bos deger bos string doner."""
    return str(BUILD_SHA if value is None else value or "")[:7]
