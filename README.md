# Caramell Dansen Terminal Player 🍭✨

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)

High-performance, flicker-free, 24-bit TrueColor **Caramelldansen** terminal player featuring **Dansen Loop** mode!

Inspired by [Ohualtex/bad-apple](https://github.com/Ohualtex/bad-apple).

---

## Features

- **24-bit TrueColor Rendering:**
  - `halfblock` (Default): Uses half-block characters (`▀`, `▄`) with 24-bit TrueColor for near-square pixels and stunning visual fidelity.
  - `color-ascii`: Classic ASCII character brightness ramp combined with full RGB color.
  - `braille`: High-resolution Unicode Braille (2x4 dot matrix) rendering.
  - `ascii`: Nostalgic monochrome ASCII shading.
- **Dansen Loop Mode (Infinite Loop):**
  - Starts directly in the iconic Mai & Mii chorus dance sequence and loops seamlessly without stutter or glitches.
  - Toggle between the dance loop and the full music video using the `L` key or CLI flags.
- **Zero-CPU Binary Cache Engine (CDBP v1):**
  - Streams from a pre-rendered, zlib-compressed RGB binary container (`caramell_dansen.bin`) for <1% CPU consumption and instantaneous seek times.
- **Flicker-Free Terminal Experience:**
  - Uses Alternate Screen Buffer (`\033[?1049h`), cursor hiding, and non-blocking I/O.
- **Responsive Sizing & Interactive Scrubber:**
  - Automatically respects 16:9 aspect ratio, centers video in any terminal window, and renders a live HUD status bar.

---

## Controls

| Key | Action |
|:---|:---|
| **Space** | Pause / Resume |
| **M** | Cycle Render Mode (`halfblock` → `color-ascii` → `braille` → `ascii`) |
| **C** | Toggle Color Mode (TrueColor RGB ↔ Monochrome) |
| **L** | Toggle **Dansen Loop** mode |
| **Right Arrow ($\rightarrow$)** | Seek forward 5 seconds |
| **Left Arrow ($\leftarrow$)** | Seek backward 5 seconds |
| **R** | Restart playback |
| **Q / Esc** | Quit cleanly |

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/your-username/caramell-dansen.git
cd caramell-dansen

# Run with virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start playback (starts directly in Dansen Loop mode)
python3 main.py

# Play full music video from start
python3 main.py --full

# Select rendering mode
python3 main.py --mode color-ascii
```

---

## CLI Options

```text
usage: main.py [-h] [--mode {halfblock,color-ascii,braille,ascii}] [--no-color] [--loop] [--full] [--no-audio] [--build-cache]

options:
  -h, --help            show this help message and exit
  --mode {halfblock,color-ascii,braille,ascii}
                        Rendering mode (default: halfblock)
  --no-color, --mono    Disable TrueColor rendering and run in monochrome
  --loop                Start in infinite Dansen Loop mode (default: True)
  --full                Play full music video from start to finish
  --no-audio            Mute audio and run on internal clock
  --build-cache         Force rebuild CDBP binary cache
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
