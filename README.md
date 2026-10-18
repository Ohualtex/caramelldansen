# Caramelldansen in Terminal 🍭✨

[![PyPI version](https://img.shields.io/pypi/v/caramelldansen.svg)](https://pypi.org/project/caramelldansen/)
[![Python Version](https://img.shields.io/pypi/pyversions/caramelldansen.svg)](https://pypi.org/project/caramelldansen/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)](https://github.com/Ohualtex/caramelldansen)

High-performance, flicker-free, 24-bit TrueColor **Caramelldansen** terminal player!

Built with a modular **Platform Abstraction Layer (PAL)** and **Audio Master Clock** architecture, providing zero-configuration, cross-platform audio and rendering on **macOS, Windows, and Linux**.

---

## Features

- **24-bit TrueColor Rendering:**
  - `halfblock` (Default): Uses half-block characters (`▀`, `▄`) with 24-bit TrueColor for near-square pixels and stunning visual fidelity.
  - `color-ascii`: Classic ASCII character brightness ramp combined with full RGB color.
  - `braille`: High-resolution Unicode Braille (2x4 dot matrix) rendering.
  - `ascii`: Nostalgic monochrome ASCII shading.
- **Audio Master Clock Engine:**
  - Video rendering is strictly synchronized to hardware audio playback time for flawless rhythm alignment and zero audio-video drift.
- **Zero-CPU Binary Cache Engine (CDBP v1):**
  - Streams from a pre-rendered, zlib-compressed RGB binary container (`caramell_dansen.bin`) for <1% CPU consumption and instantaneous seek times.
- **Automatic Asset Provisioning:**
  - Installs in seconds as a featherlight (<40 KB) PyPI wheel! Video and audio assets are automatically downloaded on first launch with live progress bar and MD5 verification.
- **Flicker-Free Terminal Experience:**
  - Uses Alternate Screen Buffer (`\033[?1049h`), cursor hiding, Win32 VT100 processing, and non-blocking I/O.
- **Responsive Sizing & Interactive Scrubber:**
  - Automatically respects 16:9 aspect ratio, centers video in any terminal window, and renders an adaptive live HUD status bar.

---

## Controls

| Key | Action |
| :--- | :--- |
| **Space** | Pause / Resume |
| **M** | Cycle Render Mode (`halfblock` → `color-ascii` → `braille` → `ascii`) |
| **C** | Toggle Color Mode (TrueColor RGB ↔ Monochrome) |
| **Right Arrow ($\rightarrow$)** | Seek forward 5 seconds |
| **Left Arrow ($\leftarrow$)** | Seek backward 5 seconds |
| **R** | Restart playback from beginning |
| **Q / Esc** | Quit cleanly |

---

## Installation & Quick Start

### Option 1: Install from PyPI (Recommended)

```bash
pip install caramelldansen
```

Run directly from any terminal:
```bash
caramelldansen
```

### Option 2: Run from Source

```bash
# Clone the repository
git clone https://github.com/Ohualtex/caramelldansen.git
cd caramelldansen

# Install dependencies
pip install -r requirements.txt

# Start playback (plays full music video from 00:00)
python main.py

# Select rendering mode
python main.py --mode color-ascii
```

---

## CLI Options

```text
usage: caramelldansen [-h] [--mode {halfblock,color-ascii,braille,ascii}] [--no-color] [--no-audio] [--build-cache]

options:
  -h, --help            show this help message and exit
  --mode {halfblock,color-ascii,braille,ascii}
                        Rendering mode (default: halfblock)
  --no-color, --mono    Disable TrueColor rendering and run in monochrome
  --no-audio            Mute audio and run on internal clock
  --build-cache         Force rebuild CDBP binary cache
```

---

## Terminal Display Tips

### macOS Terminal.app (Gapless Half-Block Display)
The default macOS `Terminal.app` adds vertical line leading (font spacing) between character rows. For a gapless, seamless display:
1. Open **Terminal** → **Settings** (`Cmd + ,`) → **Profiles** → **Text**.
2. Click **Change...** under Font.
3. Set the **Line Spacing** slider to **`0.80`**.
4. Alternatively, press **`M`** in-player to switch to **Braille mode** (which is naturally immune to line spacing), or use modern GPU-accelerated terminals like [Ghostty](https://ghostty.org/), [iTerm2](https://iterm2.com/), or [Kitty](https://sw.kovidgoyal.net/kitty/).

### Windows Terminal
Runs out of the box in [Windows Terminal](https://github.com/microsoft/terminal), PowerShell, and Command Prompt with 24-bit TrueColor enabled via Win32 Virtual Terminal Processing.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
