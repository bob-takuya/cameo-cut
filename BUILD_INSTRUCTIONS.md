# CameoCut Build Instructions

## Recent Changes (2026-02-11)

### Fixed Move To Function with Absolute Coordinates

The move_to function has been fixed to use **absolute coordinates** from the device home position:

1. **Added PA (Plot Absolute) command** to explicitly ensure absolute coordinate mode
2. **Improved coordinate logging** to track transformations from canvas to device
3. **Clarified coordinate system**:
   - Origin is at top-left (0,0)
   - X increases to the right
   - Y increases downward
   - All coordinates are absolute from device home position

### Modified Files:
- `/Users/takuyaitabashi/cameo-cut/src/device/cameo.py` - Line 423-483 (move_to function)
  - Added PA command for absolute coordinates
  - Enhanced logging to show coordinate transformations

- `/Users/takuyaitabashi/cameo-cut/src/ui/main_window.py` - Line 459-478 (_on_tool_position_changed)
  - Added debug logging for canvas click coordinates
  - Clarified that coordinates are absolute from home

## Running the App

### Option 1: Run from Source (Recommended for Development)
```bash
cd /Users/takuyaitabashi/cameo-cut
python3 src/main.py
```

### Option 2: Use the App Bundle
The app is located at: `~/Applications/CameoCut.app`

To launch:
```bash
open ~/Applications/CameoCut.app
```

Or drag it to your Dock for quick access.

### Option 3: Move to System Applications (requires admin password)
```bash
sudo cp -R ~/Applications/CameoCut.app /Applications/
```

## About the App Bundle

The CameoCut.app bundle was created using AppleScript (osacompile) rather than py2app due to build issues with py2app's recursion handling. The app is a simple launcher that runs:

```bash
/Users/takuyaitabashi/.pyenv/versions/3.10.12/bin/python3 /Users/takuyaitabashi/cameo-cut/src/main.py
```

This means **any changes to the source code are immediately reflected** when you launch the app - no rebuild needed!

## Coordinate System

The app now uses **absolute coordinates** for all device movements:

1. Canvas coordinates (mm) are in Cameo coordinate system: origin at top-left, Y increases downward
2. Clicking on canvas converts position to SU (1 SU = 0.05mm, 20 SU = 1mm)
3. Device receives **absolute coordinates** from home position via M command with PA mode

Example:
- Canvas click at (10mm, 20mm) → converts to (200SU, 400SU)
- Sends: `PA` (Plot Absolute), then `M400,200` (note: Y first, X second in GPGL)
- Device moves to absolute position (10mm, 20mm) from home (top-left corner)

## Debugging

Console output shows coordinate transformations:
```
*** Canvas click: (10.0, 20.0)mm -> (200, 400)SU (absolute from home) ***
```

Check the console/terminal for detailed GPGL command logging when moving the tool.

## Previous Y-Axis Flip Implementation

All DXF entity conversions now flip Y-axis for GPGL compatibility:
- DXF: Y increases upward (bottom-left origin)
- GPGL: Y increases downward (top-left origin)
- Conversion: new_y = offset_y - old_y, where offset_y = bounds.max_y

This ensures DXF designs appear correctly oriented on the Cameo.
