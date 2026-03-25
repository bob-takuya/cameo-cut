"""
Color-based settings panel for CameoCut

Allows users to configure cutting settings for each color
detected in the DXF file.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Callable, Optional
from enum import Enum, auto

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSlider, QSpinBox, QFrame,
    QScrollArea, QGroupBox, QPushButton, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPalette


# DXF color index to RGB mapping (AutoCAD colors)
DXF_COLOR_RGB: Dict[int, tuple] = {
    0: (0, 0, 0),        # Black (ByBlock)
    1: (255, 0, 0),      # Red
    2: (255, 255, 0),    # Yellow
    3: (0, 255, 0),      # Green
    4: (0, 255, 255),    # Cyan
    5: (0, 0, 255),      # Blue
    6: (255, 0, 255),    # Magenta
    7: (255, 255, 255),  # White
    8: (128, 128, 128),  # Dark Gray
    9: (192, 192, 192),  # Light Gray
}


@dataclass
class ColorSetting:
    """Settings for a single color"""
    color_index: int
    tool: int = 2  # Default to Tool 2 (pen) to avoid accidental cutting
    force: int = 10  # Lower force for pen
    speed: int = 10
    depth: int = 0  # No depth for pen
    passes: int = 1
    entity_count: int = 0
    skip: bool = False  # Whether to skip this color


class ColorSettingWidget(QFrame):
    """Widget for configuring a single color's settings"""

    settings_changed = pyqtSignal(int)  # Emits color index when changed

    def __init__(self, color_index: int, entity_count: int = 0, parent=None):
        super().__init__(parent)
        self.color_index = color_index
        self._settings = ColorSetting(color_index, entity_count=entity_count)
        self._setup_ui()

    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setLineWidth(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header with color swatch and count
        header = QHBoxLayout()

        # Color swatch
        self.color_swatch = QLabel()
        self.color_swatch.setFixedSize(24, 24)
        self._update_color_swatch()
        header.addWidget(self.color_swatch)

        # Color name and count
        color_name = self._get_color_name()
        self.header_label = QLabel(f"{color_name} ({self._settings.entity_count} entities)")
        self.header_label.setStyleSheet("font-weight: bold;")
        header.addWidget(self.header_label)
        header.addStretch()

        layout.addLayout(header)

        # Tool selection
        tool_layout = QHBoxLayout()
        tool_layout.addWidget(QLabel("Tool:"))
        self.tool_combo = QComboBox()
        self.tool_combo.addItems(["1 - AutoBlade (Cutter)", "2 - Pen/Accessory"])
        self.tool_combo.setCurrentIndex(1)  # Default to Tool 2 (Pen)
        self.tool_combo.currentIndexChanged.connect(self._on_settings_changed)
        tool_layout.addWidget(self.tool_combo)

        # Skip checkbox
        self.skip_checkbox = QCheckBox("Skip this color")
        self.skip_checkbox.setChecked(self._settings.skip)  # Set initial state
        self.skip_checkbox.stateChanged.connect(self._on_skip_changed)
        tool_layout.addWidget(self.skip_checkbox)
        layout.addLayout(tool_layout)

        # Settings container (hidden when action is Skip)
        self.settings_container = QWidget()
        settings_layout = QVBoxLayout(self.settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(4)

        # Force slider
        force_layout = QHBoxLayout()
        force_layout.addWidget(QLabel("Force:"))
        self.force_slider = QSlider(Qt.Orientation.Horizontal)
        self.force_slider.setRange(1, 33)
        self.force_slider.setValue(self._settings.force)
        self.force_slider.valueChanged.connect(self._on_settings_changed)
        force_layout.addWidget(self.force_slider)
        self.force_label = QLabel(str(self._settings.force))
        self.force_label.setFixedWidth(30)
        force_layout.addWidget(self.force_label)
        settings_layout.addLayout(force_layout)

        # Speed slider
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 30)
        self.speed_slider.setValue(self._settings.speed)
        self.speed_slider.valueChanged.connect(self._on_settings_changed)
        speed_layout.addWidget(self.speed_slider)
        self.speed_label = QLabel(str(self._settings.speed))
        self.speed_label.setFixedWidth(30)
        speed_layout.addWidget(self.speed_label)
        settings_layout.addLayout(speed_layout)

        # Depth slider
        depth_layout = QHBoxLayout()
        depth_layout.addWidget(QLabel("Depth:"))
        self.depth_slider = QSlider(Qt.Orientation.Horizontal)
        self.depth_slider.setRange(0, 10)
        self.depth_slider.setValue(self._settings.depth)
        self.depth_slider.valueChanged.connect(self._on_settings_changed)
        depth_layout.addWidget(self.depth_slider)
        self.depth_label = QLabel(str(self._settings.depth))
        self.depth_label.setFixedWidth(30)
        depth_layout.addWidget(self.depth_label)
        settings_layout.addLayout(depth_layout)

        # Passes spinner
        passes_layout = QHBoxLayout()
        passes_layout.addWidget(QLabel("Passes:"))
        self.passes_spin = QSpinBox()
        self.passes_spin.setRange(1, 10)
        self.passes_spin.setValue(self._settings.passes)
        self.passes_spin.valueChanged.connect(self._on_settings_changed)
        passes_layout.addWidget(self.passes_spin)
        passes_layout.addStretch()
        settings_layout.addLayout(passes_layout)

        layout.addWidget(self.settings_container)

    def _on_skip_changed(self, state):
        """Handle skip checkbox change"""
        from PyQt6.QtCore import Qt
        self._settings.skip = (state == Qt.CheckState.Checked.value)
        # Hide settings when skipped
        self.settings_container.setVisible(not self._settings.skip)
        logger.debug("Color %d skip → %s", self.color_index, self._settings.skip)
        self._on_settings_changed()

    def _update_color_swatch(self):
        """Update the color swatch display"""
        rgb = DXF_COLOR_RGB.get(self.color_index, (128, 128, 128))
        self.color_swatch.setStyleSheet(
            f"background-color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]}); "
            f"border: 1px solid #888; border-radius: 4px;"
        )

    def _get_color_name(self) -> str:
        """Get human-readable color name"""
        names = {
            0: "Black",
            1: "Red",
            2: "Yellow",
            3: "Green",
            4: "Cyan",
            5: "Blue",
            6: "Magenta",
            7: "White",
            8: "Dark Gray",
            9: "Light Gray",
        }
        return names.get(self.color_index, f"Color {self.color_index}")

    def _on_settings_changed(self):
        """Handle any setting change"""
        self._settings.tool = self.tool_combo.currentIndex() + 1
        self._settings.force = self.force_slider.value()
        self._settings.speed = self.speed_slider.value()
        self._settings.depth = self.depth_slider.value()
        self._settings.passes = self.passes_spin.value()
        self._settings.skip = self.skip_checkbox.isChecked()  # CRITICAL: Preserve skip state!

        # Update labels
        self.force_label.setText(str(self._settings.force))
        self.speed_label.setText(str(self._settings.speed))
        self.depth_label.setText(str(self._settings.depth))

        self.settings_changed.emit(self.color_index)

    def get_settings(self) -> ColorSetting:
        """Get current settings"""
        return self._settings

    def set_settings(self, settings: ColorSetting):
        """Apply settings"""
        self._settings = settings

        # Update UI
        self.tool_combo.setCurrentIndex(settings.tool - 1)
        self.skip_checkbox.setChecked(settings.skip)
        self.force_slider.setValue(settings.force)
        self.speed_slider.setValue(settings.speed)
        self.depth_slider.setValue(settings.depth)
        self.passes_spin.setValue(settings.passes)

    def set_entity_count(self, count: int):
        """Update entity count display"""
        self._settings.entity_count = count
        color_name = self._get_color_name()
        self.header_label.setText(f"{color_name} ({count} entities)")


class ColorSettingsPanel(QScrollArea):
    """Panel containing settings for all colors in the design"""

    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color_widgets: Dict[int, ColorSettingWidget] = {}
        self._presets: List[dict] = []
        self._setup_ui()

    def set_presets(self, presets: List[dict]):
        """Set available material presets"""
        self._presets = presets

    def _setup_ui(self):
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container widget
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(4, 4, 4, 4)
        self.container_layout.setSpacing(8)

        # Title
        title = QLabel("Color Settings")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.container_layout.addWidget(title)

        # Placeholder when no colors
        self.placeholder = QLabel("Load a DXF file to configure color settings")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet("color: #888; padding: 20px;")
        self.container_layout.addWidget(self.placeholder)

        self.container_layout.addStretch()

        self.setWidget(self.container)

    def set_colors(self, color_counts: Dict[int, int], default_mappings: Optional[Dict[str, dict]] = None):
        """Set the colors to display

        Args:
            color_counts: Dict mapping color index to entity count
            default_mappings: Optional default settings by color
        """
        # Clear existing widgets
        for widget in self._color_widgets.values():
            widget.deleteLater()
        self._color_widgets.clear()

        # Hide placeholder
        self.placeholder.setVisible(len(color_counts) == 0)

        # Create widgets for each color with consistent defaults
        for color_index in sorted(color_counts.keys()):
            count = color_counts[color_index]
            widget = ColorSettingWidget(color_index, count, self)
            widget.settings_changed.connect(lambda _: self.settings_changed.emit())

            # No color-specific defaults - use ColorSetting defaults for all
            self._color_widgets[color_index] = widget

            # Insert before the stretch
            self.container_layout.insertWidget(
                self.container_layout.count() - 1, widget
            )

    def get_all_settings(self) -> Dict[str, dict]:
        """Get settings for all colors as dict"""
        result = {}
        for color, widget in self._color_widgets.items():
            setting = widget.get_settings()
            result[str(color)] = {
                "skip": setting.skip,
                "tool": setting.tool,
                "force": setting.force,
                "speed": setting.speed,
                "depth": setting.depth,
                "passes": setting.passes,
            }
        return result

    def clear(self):
        """Clear all color settings"""
        for widget in self._color_widgets.values():
            widget.deleteLater()
        self._color_widgets.clear()
        self.placeholder.setVisible(True)
