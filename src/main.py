#!/usr/bin/env python3
"""
CameoCut - Lightweight DXF to Silhouette Cameo 5 sender

A fast, lightweight application for sending DXF cutting data to
Silhouette Cameo 5 with color-based cutting settings.
"""

import sys
import logging
from pathlib import Path

# Ensure src directory is in path for imports
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon


def get_icon_path() -> Path:
    """Get the path to the application icon"""
    base_dir = Path(__file__).parent.parent
    icon_locations = [
        base_dir / "resources" / "icons" / "cameocut.icns",
        base_dir / "resources" / "icons" / "cameocut.png",
    ]

    for path in icon_locations:
        if path.exists():
            return path

    return icon_locations[0]


def setup_logging():
    """Configure logging for the application"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )


def main():
    """Main entry point"""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting CameoCut")

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("CameoCut")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("CameoCut")

    # Set application icon (for Dock on macOS)
    icon_path = get_icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
        logger.info(f"Icon loaded: {icon_path}")

    # Set application style
    app.setStyle("Fusion")

    # Import here to avoid circular imports
    from ui.main_window import MainWindow

    # Create and show main window
    window = MainWindow()
    window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    # Handle command line arguments (open file if provided)
    args = app.arguments()
    if len(args) > 1:
        filepath = Path(args[1])
        if filepath.exists() and filepath.suffix.lower() == '.dxf':
            window._load_dxf(filepath)

    logger.info("CameoCut ready")

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
