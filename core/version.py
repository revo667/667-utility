
from __future__ import annotations

APP_VERSION = "0.3.1"

#: CI paketleme oncesi bu satiri yeniden yazar (build.yml -> "Surum damgasi").
BUILD_SHA = ""


def short_sha(value: str | None = None) -> str:
    return str(BUILD_SHA if value is None else value or "")[:7]
