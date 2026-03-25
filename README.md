# CameoCut

A lightweight macOS controller for the **Silhouette Cameo 5** cutting plotter.
Built as a faster, open alternative to Silhouette Studio for DXF-based workflows.

## Features

- Load and preview DXF files
- Per-color tool settings (force, speed, blade depth, passes)
- USB and Bluetooth (BLE) connection support
- Export / import GPGL files for debugging
- Drag-to-position canvas (visual preview; physical origin set on device)

## Requirements

| Package | Version |
|---------|---------|
| Python  | ≥ 3.10  |
| PyQt6   | ≥ 6.4   |
| pyusb   | ≥ 1.2   |
| bleak   | ≥ 0.21  |

## Installation

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/cameo-cut.git
cd cameo-cut

# 2. Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

> **USB on macOS:** `pyusb` requires `libusb`.
> Install via Homebrew: `brew install libusb`

## Usage

```bash
python3 run.py
```

1. Open a DXF file (File → Open or drag-and-drop).
2. Configure per-color settings in the right panel (tool, force, speed, depth).
3. Connect the Cameo 5 via USB (click **Connect**) or Bluetooth (click **Bluetooth…**).
4. Use the device's own controls to set the physical cut origin on the mat.
5. Click **Send to Cutter**.

## Coordinate System

CameoCut normalises the DXF design so its bounding-box starts at `(0, 0)`.
The physical start position is **always determined by the device** (Home / origin
button on the Cameo), exactly like Silhouette Studio — no software offset is applied.

## Building the .app bundle

```bash
pip install pyinstaller
python3 setup.py py2app   # or see BUILD_INSTRUCTIONS.md
```

## License

MIT License — see [LICENSE](LICENSE) for details.

Copyright © 2026 Takuya Itabashi
