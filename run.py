#!/usr/bin/env python3
"""
Development launcher for CameoCut

This script sets up the environment and launches the application
with proper icon display on macOS Dock.
"""

import sys
import os
from pathlib import Path

# Add src to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

# Set app name for macOS Dock (must be done before QApplication)
if sys.platform == 'darwin':
    # This helps with Dock icon display in development mode
    try:
        from Foundation import NSBundle
        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        if info:
            info['CFBundleName'] = 'CameoCut'
    except ImportError:
        pass  # pyobjc not installed, icon may not show in Dock

# Import and run main
from main import main

if __name__ == "__main__":
    main()
