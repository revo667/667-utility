"""Time Machine yerel snapshot yonetimi.

Neden ayri modul: snapshot'lar dosya degil, APFS metadata. shutil ile silinmezler,
silinmemelidirler de. Tek dogru arayuz tmutil.

Tasarim kurallari:
  1. Asla `deletelocalsnapshots` ile toplu silme. Sadece `thinlocalsnapshots`
     ile hedeflenen kadar yer ac - sistem en eskisinden baslar.
  2. MIN_AGE_HOURS'tan yeni snapshot'a dokunma. Dun sabah sildigin dosya orada.
  3. Harici yedek hedefi tanimli degilse kullaniciyi uyar: snapshot onun TEK yedegi.
  4. Sistem guncellemesi sirasinda calistirma (snapshot geri donus noktasidir).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.platform_utils import IS_MACOS, human_size

#: Bu yastan yeni snapshot'lar korunur. 24 saat = "dun yaptigim hatayi geri alabilirim".
MIN_AGE_HOURS = 24

#: tmutil cagrilari icin ust sinir. Snapshot islemleri yavas olabilir.
_TIMEOUT = 120

_SNAPSHOT_RE = re.compile(
    r"com\.apple\.TimeMachine\.(\d{4}-\d{2}-\d{2}-\d{6})(?:\.local)?"
)


@dataclass(frozen=True)
class Snapshot:
    name: str
    created: datetime | None

    @property
    def age(self) -> timedelta | None:
        if self.created is None:
            return None
        return datetime.now() - self.created

    @property
    def age_hours(self) -> float:
        age = self.age
        return age.total_seconds() / 3600 if age else 0.0

    @property
    def is_protected(self) -> bool:
        """Cok yeni = dokunma."""
        return self.created is None or self.age_hours < MIN_AGE_HOURS

    @property
    def pretty_age(self) -> str:
        if self.created is None:
            return "bilinmiyor"
        hours = self.age_hours
        if hours < 24:
            return f"{hours:.0f} saat once"
        return f"{hours / 24:.0f} gun once"


@dataclass(frozen=True)
class SnapshotReport:
    available: bool
    snapshots: tuple[Snapshot, ...]
    has_backup_destination: bool
    purgeable_bytes: int
    error: str = ""

    @property
    def thinnable(self) -> tuple[Snapshot, ...]:
        return tuple(s for s in self.snapshots if not s.is_protected)

    @property
    def protected(self) -> tuple[Snapshot, ...]:
        return tuple(s for s in self.snapshots if s.is_protected)

    @property
    def risk_level(self) -> str:
        """Yedek diski yoksa bu snapshot'lar tek kurtarma yolu."""
        if not self.has_backup_destination:
            return "danger"
        return "warning"

    def summary(self) -> str:
        if not self.available:
            return self.error or "Yerel snapshot bulunamadi."
        total = len(self.snapshots)
        thinnable = len(self.thinnable)
        base = f"{total} yerel snapshot ({thinnable} tanesi {MIN_AGE_HOURS} saatten eski)."
        if self.purgeable_bytes:
            base += f" Tahmini geri kazanilabilir: {human_size(self.purgeable_bytes)}."
        if not self.has_backup_destination:
            base += (
                "\nUYARI: Tanimli bir Time Machine yedek diski yok. "
                "Bu snapshot'lar su an tek kurtarma noktan."
            )
        return base


def _run(args: list[str]) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=_TIMEOUT, check=False
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode == 0, output.strip()
    except FileNotFoundError:
        return False, "tmutil bulunamadi."
    except subprocess.TimeoutExpired:
        return False, "tmutil zaman asimina ugradi."
    except OSError as exc:
        return False, str(exc)


def _parse_snapshots(output: str) -> tuple[Snapshot, ...]:
    found: list[Snapshot] = []
    for match in _SNAPSHOT_RE.finditer(output):
        stamp = match.group(1)
        try:
            created = datetime.strptime(stamp, "%Y-%m-%d-%H%M%S")
        except ValueError:
            created = None
        found.append(Snapshot(name=match.group(0), created=created))
    found.sort(key=lambda s: s.created or datetime.min)
    return tuple(found)


def has_backup_destination() -> bool:
    """Tanimli bir Time Machine hedefi var mi? Yoksa snapshot silmek daha riskli."""
    ok, output = _run(["tmutil", "destinationinfo"])
    if not ok:
        return False
    return "Name" in output or "URL" in output or "ID" in output


def estimate_purgeable() -> int:
    """Snapshot'larin serbest birakabilecegi tahmini alan.

    APFS'te snapshot alani 'purgeable' sayilir. df ile container free space
    arasindaki fark kaba bir tahmindir - kesin rakam vermiyoruz, vermemeliyiz.
    """
    ok, output = _run(["diskutil", "info", "-plist", "/System/Volumes/Data"])
    if not ok:
        return 0
    try:
        import plistlib

        data = plistlib.loads(output.encode("utf-8", errors="replace"))
        container_free = int(data.get("APFSContainerFree", 0))
        volume_free = int(data.get("FreeSpace", 0))
        return max(0, container_free - volume_free)
    except Exception:
        return 0


def scan_snapshots() -> SnapshotReport:
    """Yerel snapshot'lari listeler. Hicbir sey silmez."""
    if not IS_MACOS:
        return SnapshotReport(False, (), False, 0, "macOS disi sistem.")

    ok, output = _run(["tmutil", "listlocalsnapshots", "/"])
    if not ok:
        return SnapshotReport(False, (), False, 0, output or "Snapshot listelenemedi.")

    snapshots = _parse_snapshots(output)
    if not snapshots:
        return SnapshotReport(False, (), has_backup_destination(), 0,
                              "Yerel snapshot yok. Temizlenecek bir sey de yok.")

    return SnapshotReport(
        available=True,
        snapshots=snapshots,
        has_backup_destination=has_backup_destination(),
        purgeable_bytes=estimate_purgeable(),
    )


def thin_snapshots(
    target_bytes: int,
    *,
    urgency: int = 1,
    dry_run: bool = True,
) -> tuple[bool, int, str]:
    """Hedeflenen kadar yer acar. En eski snapshot'tan baslar.

    urgency: 1 = en nazik (sadece gerektigi kadar sil), 4 = en agresif.
             Varsayilani 1'de birak. 4 kullanma sebebin yok.
    dry_run: True ise komut calistirilmaz, sadece ne yapilacagi doner.

    Doner: (basarili, serbest_kalan_bayt, mesaj)
    """
    if not IS_MACOS:
        return False, 0, "macOS disi sistem."
    if target_bytes <= 0:
        return False, 0, "Gecersiz hedef boyut."

    urgency = max(1, min(4, urgency))
    report = scan_snapshots()

    if not report.available:
        return False, 0, report.error
    if not report.thinnable:
        return False, 0, (
            f"Tum snapshot'lar {MIN_AGE_HOURS} saatten yeni. Korunuyorlar."
        )

    command = ["tmutil", "thinlocalsnapshots", "/", str(int(target_bytes)), str(urgency)]

    if dry_run:
        return True, 0, (
            f"[dry-run] Calistirilacak: {' '.join(command)}\n"
            f"{len(report.thinnable)} snapshot inceltme adayi."
        )

    before = shutil.disk_usage("/").free
    ok, output = _run(command)
    after = shutil.disk_usage("/").free
    freed = max(0, after - before)

    if not ok:
        return False, freed, output or "Inceltme basarisiz."
    return True, freed, f"{human_size(freed)} serbest birakildi."


def delete_snapshot(snapshot: Snapshot, *, dry_run: bool = True) -> tuple[bool, str]:
    """Tek bir snapshot'i siler. Yas korumasi burada da uygulanir.

    Normalde thin_snapshots() tercih edilmeli. Bu fonksiyon kullaniciya
    tek tek secim imkani vermek icin var.
    """
    if not IS_MACOS:
        return False, "macOS disi sistem."
    if snapshot.is_protected:
        return False, (
            f"{snapshot.name} korunuyor ({snapshot.pretty_age}, "
            f"{MIN_AGE_HOURS} saatten yeni)."
        )

    match = _SNAPSHOT_RE.match(snapshot.name)
    if not match:
        return False, "Gecersiz snapshot adi."
    stamp = match.group(1)

    if dry_run:
        return True, f"[dry-run] tmutil deletelocalsnapshots {stamp}"

    ok, output = _run(["tmutil", "deletelocalsnapshots", stamp])
    return ok, output or ("Silindi." if ok else "Silinemedi.")
