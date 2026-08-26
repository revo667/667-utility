# 667 Utility

Windows ve macOS icin sistem optimizasyon, uygulama kurulum/kaldirma ve disk
temizleme araci. PySide6 ile yazildi.

<p align="center">
  <sub>revo667.com</sub>
</p>

---

## Ozellikler

Sidebar'daki sayfalar calistigin platforma gore otomatik belirlenir.

| Sayfa | Platform | Ne yapar |
|---|---|---|
| **Dashboard** | Hepsi | CPU, RAM, disk ve calisma suresi ozeti |
| **Optimizer** | Windows | Servis, registry ve guc plani tweak'leri — her biri geri alinabilir |
| **Installer** | Windows / Linux | `winget` uzerinden toplu uygulama kurulumu |
| **Installer** | macOS | Homebrew formula ve cask arama/kurulum |
| **Uninstaller** | Windows | Kurulu programlari kaldirma + UWP bloatware temizligi |
| **Uninstaller** | macOS | Uygulama + artik dosyalarini birlikte kaldirma |
| **Cleaner** | macOS | Onbellek, log, Xcode artiklari — kategorili ve boyutlu tarama |
| **Snapshots** | macOS | Time Machine yerel snapshot yonetimi |
| **Ayarlar** | Hepsi | Animasyon, yenileme araligi ve onay tercihleri |

## Kurulum

```bash
git clone https://github.com/revo667/667-utility.git
cd 667-utility

# uv ile (onerilen — uv.lock kilitli surumleri kullanir)
uv sync
uv run main.py

# ya da pip ile
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Python 3.11 veya uzeri gerekir.

## Platform notlari

**Windows** — Optimizer ve Uninstaller yonetici hakki ister. Uygulama gerekirse
kendini UAC istemiyle yeniden baslatir; reddedersen sinirli modda acilir.

**macOS** — Cleaner ve Uninstaller `~/Library` altini okur. Ilk acilista izin
istenir. Terminal veya IDE icinden calistiriyorsan macOS izni **seni baslatan
uygulamaya** atar; uygulama bunu tespit edip System Settings'te hangi girdiyi
aramanı gerektigini soyler.

**Guvenlik** — Temizlik islemleri varsayilan olarak dosyalari **cop kutusuna
tasir**, kalici silmez. Snapshot inceltme 24 saatten yeni snapshot'lara
dokunmaz. Korumali sistem yollari (`/System`, `~/Library/Keychains`, ...) her
zaman disaridadir.

## Proje yapisi

```
core/                 Platform mantigi — Qt'ye bagimli degil
  platform_utils.py     Platform tespiti ve ortak yardimcilar
  optimizations.py      Windows tweak'leri (uygula/geri al ciftleri)
  installer.py          winget kurulumu
  uninstaller.py        Windows program kaldirma + bloatware
  search.py             winget paket arama
  mac_cleaner.py        Kural tabanli cop tarama
  mac_installer.py      Homebrew sarmalayici
  mac_uninstaller.py    Uygulama + artik kaldirma
  mac_permissions.py    TCC izin durumu
  mac_responsible.py    Izni hangi uygulamanin aldigini tespit
  mac_snapshots.py      Time Machine snapshot yonetimi

src/ui/               Arayuz
  theme.py              Renk, olcu, tipografi token'lari
  style.py              Merkezi QSS — tek stil kaynagi
  icons.py              Inline SVG ikon seti
  toast.py              Kayan bildirimler
  settings_store.py     Kalici kullanici tercihleri
  fonts.py              Paketli font yukleyici
  pages.py              Sayfa kayit defteri (platform filtreli)
  main_window.py        Kabuk: baslik cubugu, sidebar, sayfa yigini
  views/                Sayfalar
```

**Mimari kurali:** `core/` Qt bilmez, `src/ui/` sistem komutu calistirmaz.
Widget'lar inline `setStyleSheet()` cagirmaz — gorunum farki bir Qt property'si
ile ifade edilir ve secici `style.py` icine yazilir.

## Paketleme

Uc platform icin de calistirilabilir paket uretilir. **Capraz derleme yoktur** —
`.exe` Windows'ta, `.app` macOS'ta uretilmek zorundadir.

```bash
uv pip install pyinstaller
uv run pyinstaller 667utility.spec --noconfirm
```

Cikti:

| Platform | Sonuc |
|---|---|
| macOS | `dist/667 Utility.app` |
| Windows | `dist/667Utility/667Utility.exe` |
| Linux | `dist/667Utility/667Utility` |

Uretilen paketin gercekten calistigini dogrulamak icin:

```bash
./dist/667Utility/667Utility --selftest
```

Bu komut kaynak dosya yollarini (font, `.reg`, `apps.json`) kontrol eder ve
tum sayfalari kurup kapatir. Paketlemede en sik kirilan sey yollardir —
`.app`/`.exe` icinde `__file__` baska yere isaret ettigi icin dosyalar
sessizce bulunamaz olur. `core/resources.py` bunu tek noktadan cozer.

### CI

`.github/workflows/build.yml` her push'ta uc platformda paralel paket uretir
ve her birinde `--selftest` calistirir. `v*` etiketi atildiginda
(`git tag v0.2.0 && git push --tags`) `.dmg`, `.zip` ve `.tar.gz` dosyalarini
GitHub Release'e yukler.

**Imzalama** yapilmiyor. macOS'ta ilk acilista Gatekeeper engeller
(sag tik > Ac ile gecilir), Windows'ta SmartScreen uyarir. Imzalamak icin
Apple Developer uyeligi ve bir code signing sertifikasi gerekir.

## Gelistirme

```bash
pip install -r requirements-dev.txt
ruff check .          # lint
ruff check --fix .    # otomatik duzelt
```

## Lisans

MIT — bkz. [LICENSE](LICENSE).
