# 667 Utility

A Windows system optimization tool built with Python and PySide6.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.x-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-purple)

---

## Features

- **System Optimizer** — Apply performance tweaks with one click. Disable unnecessary services, telemetry, Xbox bloat, and more. Each tweak is reversible.
- **Registry Tweaks** — Apply curated `.reg` files for CPU, GPU, and system-level performance improvements.
- **BAT Tweaks** — Run pre-configured batch scripts for BCD and input delay optimizations.
- **Uninstaller** — Browse all installed programs and uninstall them. One-click Windows bloatware removal including Edge.
- **App Installer** — Install apps via winget from a categorized list. Supports multi-select and batch install.
- **Dashboard** — System info overview with applied tweak count.

---

## Requirements

- Windows 10 / 11
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- [JetBrainsMono Nerd Font](https://www.nerdfonts.com/font-downloads) installed on system
- winget (for installer feature)

---

## Installation

```bash
git clone https://github.com/revo667/667-utility.git
cd 667-utility
uv sync
```

---

## Running

Must be run as Administrator for system tweaks to apply.

```bash
uv run main.py
```

Or right-click → Run as Administrator if using Python directly.

---

## Project Structure

```
667-utility/
├── main.py
├── assets/
│   ├── bat/           # Batch scripts
│   └── regs/          # Registry tweak files
├── core/
│   ├── optimizations.py
│   ├── installer.py
│   ├── uninstaller.py
│   └── search.py
└── src/
    ├── ui/
    │   ├── main_window.py
    │   ├── style.py
    │   ├── theme.py
    │   └── views/
    │       ├── dashboard.py
    │       ├── optimizer.py
    │       ├── optimizer_card.py
    │       ├── installer.py
    │       ├── uninstaller.py
    │       └── modern_button.py
    └── apps.json
```

---

## Optimizer Tweaks

| Tweak | Description | Reversible |
|---|---|---|
| Disable SysMain | Reduces disk usage on SSDs | Yes |
| High Performance Power Plan | Maximizes CPU performance | Yes |
| Disable Telemetry | Stops Windows data collection | Yes |
| Clear Temp Files | Removes temporary files | No |
| Disable Xbox Services | Removes Xbox background processes | Yes |
| Disable Search Indexing | Reduces CPU/disk usage | Yes |
| Service Reducer | Disables unnecessary Windows services | Yes |
| Registry Tweaks | Applies all .reg performance tweaks | No |
| Lower Input Delay | Applies BCD boot tweaks via batch | No |

---

## Notes

- Some tweaks require a system restart to take full effect.
- Disabling certain services may affect rarely used Windows features.
- The bloatware remover permanently removes UWP apps including Microsoft Edge.

---

## License

MIT
