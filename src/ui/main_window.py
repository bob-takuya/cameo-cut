"""
Main window for CameoCut

The central window that integrates all components:
- DXF file loading and preview
- Color-based cutting settings
- Device connection and job sending
"""

import json
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QToolBar, QStatusBar, QFileDialog,
    QMessageBox, QLabel, QProgressDialog, QPushButton,
    QButtonGroup
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent

from ui.canvas import DXFCanvas, CanvasMode
from ui.color_settings import ColorSettingsPanel
from ui.device_panel import DevicePanel
from dxf.parser import DXFParser, DXFParseError
from dxf.entities import EntityCollection
from device.cameo import CuttingJob
from gpgl.commands import ToolSettings
from gpgl.protocol import mm_to_su
from gpgl.file_io import GPGLFile, save_gpgl, load_gpgl

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self._entities: Optional[EntityCollection] = None
        self._current_file: Optional[Path] = None
        self._presets: dict = {}

        self._load_presets()
        self._setup_ui()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()

        # Enable drag and drop
        self.setAcceptDrops(True)

    def _load_presets(self):
        """Load material presets from JSON"""
        presets_path = Path(__file__).parent.parent.parent / "resources" / "presets.json"
        try:
            with open(presets_path, 'r', encoding='utf-8') as f:
                self._presets = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load presets: {e}")
            self._presets = {"presets": [], "default_color_mappings": {}}

    def _setup_ui(self):
        """Setup the main UI layout"""
        self.setWindowTitle("CameoCut")
        self.setMinimumSize(1200, 800)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: Canvas
        self.canvas = DXFCanvas()
        splitter.addWidget(self.canvas)

        # Right side: Settings panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # Color settings
        self.color_settings = ColorSettingsPanel()
        self.color_settings.set_presets(self._presets.get("presets", []))
        right_layout.addWidget(self.color_settings, stretch=1)

        # Device panel
        self.device_panel = DevicePanel()
        right_layout.addWidget(self.device_panel)

        splitter.addWidget(right_panel)

        # Set splitter sizes (70% canvas, 30% settings)
        splitter.setSizes([840, 360])

        layout.addWidget(splitter)

    def _setup_menubar(self):
        """Setup the menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        open_action = QAction("Open DXF...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # View menu
        view_menu = menubar.addMenu("View")

        zoom_fit_action = QAction("Fit to Window", self)
        zoom_fit_action.setShortcut("Ctrl+0")
        zoom_fit_action.triggered.connect(self.canvas.fit_to_view)
        view_menu.addAction(zoom_fit_action)

        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(lambda: self.canvas.set_zoom(self.canvas._zoom * 1.2))
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(lambda: self.canvas.set_zoom(self.canvas._zoom / 1.2))
        view_menu.addAction(zoom_out_action)

        # Device menu
        device_menu = menubar.addMenu("Device")

        connect_action = QAction("Connect", self)
        connect_action.triggered.connect(self.device_panel._on_connect_clicked)
        device_menu.addAction(connect_action)

        device_menu.addSeparator()

        test_cut_action = QAction("Test Cut", self)
        test_cut_action.triggered.connect(self.device_panel._on_test_clicked)
        device_menu.addAction(test_cut_action)

    def _setup_toolbar(self):
        """Setup the toolbar"""
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Open button
        open_btn = QAction("Open DXF", self)
        open_btn.triggered.connect(self._on_open_file)
        toolbar.addAction(open_btn)

        toolbar.addSeparator()

        # GPGL Import/Export
        import_gpgl_btn = QAction("Import GPGL", self)
        import_gpgl_btn.triggered.connect(self._on_import_gpgl)
        toolbar.addAction(import_gpgl_btn)

        export_gpgl_btn = QAction("Export GPGL", self)
        export_gpgl_btn.triggered.connect(self._on_export_gpgl)
        toolbar.addAction(export_gpgl_btn)

        toolbar.addSeparator()

        # Mode toggle buttons
        self.tool_mode_btn = QPushButton("Tool Position")
        self.tool_mode_btn.setCheckable(True)
        self.tool_mode_btn.setChecked(True)
        self.tool_mode_btn.setStyleSheet("""
            QPushButton { padding: 4px 8px; }
            QPushButton:checked { background-color: #4CAF50; color: white; }
        """)
        self.tool_mode_btn.clicked.connect(lambda: self._set_canvas_mode(CanvasMode.TOOL_POSITION))
        toolbar.addWidget(self.tool_mode_btn)

        self.drag_mode_btn = QPushButton("Design Drag")
        self.drag_mode_btn.setCheckable(True)
        self.drag_mode_btn.setStyleSheet("""
            QPushButton { padding: 4px 8px; }
            QPushButton:checked { background-color: #FF9800; color: white; }
        """)
        self.drag_mode_btn.clicked.connect(lambda: self._set_canvas_mode(CanvasMode.DESIGN_DRAG))
        toolbar.addWidget(self.drag_mode_btn)

        toolbar.addSeparator()

        # Send button
        self.send_action = QAction("Send to Cutter", self)
        self.send_action.setEnabled(False)
        self.send_action.triggered.connect(self._on_send)
        toolbar.addAction(self.send_action)

    def _setup_statusbar(self):
        """Setup the status bar"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        # Entity count label
        self.entity_count_label = QLabel("No file loaded")
        self.statusbar.addWidget(self.entity_count_label)

        # Size label
        self.size_label = QLabel("")
        self.statusbar.addPermanentWidget(self.size_label)

        # Device status
        self.device_status_label = QLabel("Disconnected")
        self.statusbar.addPermanentWidget(self.device_status_label)

    def _connect_signals(self):
        """Connect signals between components"""
        # Color settings changed -> update canvas
        self.color_settings.settings_changed.connect(self._on_settings_changed)

        # Device connection changed
        self.device_panel.connection_changed.connect(self._on_connection_changed)
        self.device_panel.job_completed.connect(self._on_job_completed)

        # Tool position changed -> move device
        self.canvas.tool_position_changed.connect(self._on_tool_position_changed)

    def _on_open_file(self):
        """Handle open file action"""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open DXF File",
            "",
            "DXF Files (*.dxf);;All Files (*)"
        )

        if filepath:
            self._load_dxf(Path(filepath))

    def _load_dxf(self, filepath: Path):
        """Load a DXF file"""
        try:
            parser = DXFParser()
            self._entities = parser.parse_file(filepath)
            self._current_file = filepath

            # Update canvas
            self.canvas.set_entities(self._entities)
            self.canvas.fit_to_view()

            # Update color settings
            colors = self._entities.get_colors()
            color_counts = {}
            for color in colors:
                color_counts[color] = len(self._entities.get_by_color(color))

            self.color_settings.set_colors(
                color_counts,
                self._presets.get("default_color_mappings", {})
            )

            # Update status bar
            total = len(self._entities)
            self.entity_count_label.setText(f"{total} entities")

            bounds = self._entities.get_bounding_box()
            if bounds:
                width = bounds.max_x - bounds.min_x
                height = bounds.max_y - bounds.min_y
                self.size_label.setText(f"{width:.1f} x {height:.1f} mm")

            # Update window title
            self.setWindowTitle(f"CameoCut - {filepath.name}")

            # Enable send if connected
            self._update_send_enabled()

            logger.info(f"Loaded {filepath}: {total} entities")

        except DXFParseError as e:
            QMessageBox.critical(self, "Error", f"Failed to load DXF file:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error:\n{e}")
            logger.exception("Error loading DXF")

    def _on_settings_changed(self):
        """Handle color settings changed"""
        # Update canvas colors based on skip settings
        if self._entities:
            settings = self.color_settings.get_all_settings()
            skip_colors = set()
            for color_str, setting in settings.items():
                if setting.get("skip", False):
                    skip_colors.add(int(color_str))

            # Could update canvas to dim skipped colors
            self.canvas.update()

    def _on_connection_changed(self, connected: bool):
        """Handle device connection changed"""
        if connected:
            self.device_status_label.setText("Connected")
            self.device_status_label.setStyleSheet("color: #4CAF50;")
        else:
            self.device_status_label.setText("Disconnected")
            self.device_status_label.setStyleSheet("color: #888;")

        self._update_send_enabled()

    def _on_job_completed(self, success: bool):
        """Handle job completed"""
        if success:
            self.statusbar.showMessage("Job completed successfully", 5000)
        else:
            self.statusbar.showMessage("Job failed", 5000)

    def _update_send_enabled(self):
        """Update send button enabled state"""
        can_send = (
            self._entities is not None and
            len(self._entities) > 0 and
            self.device_panel.is_connected
        )
        self.send_action.setEnabled(can_send)

        # Also update device panel
        if can_send:
            job = self._create_job()
            self.device_panel.set_job(job)
        else:
            self.device_panel.set_job(None)

    def _create_job(self) -> Optional[CuttingJob]:
        """Create a cutting job from current entities and settings"""
        if not self._entities:
            return None

        settings = self.color_settings.get_all_settings()
        logger.debug("Color settings: %s", settings)

        from gpgl.commands import GPGLCommandBuilder
        builder = GPGLCommandBuilder()

        # CRITICAL: Home first to establish known position
        builder.home()                  # H - Home to origin

        # Initialize device (required before tool selection)
        builder.set_orientation(False)  # FN0 - Portrait
        builder.set_origin(0)           # SO0 - Origin

        # Normalize DXF coordinates to device origin (0, 0).
        #
        # The Silhouette Cameo workflow is:
        #   1. Home (H) moves the tool to the physical origin chosen by the user.
        #   2. All coordinates are absolute from that origin.
        #   3. The software should NOT apply any additional offset — the user
        #      positions the material on the mat and uses the device's own
        #      controls to set the physical start point.
        #
        # We therefore only normalize the DXF so that the design's bounding-box
        # minimum maps to (0, 0), and flip the Y axis (DXF: Y-up, GPGL: Y-down).
        bounds = self._entities.get_bounding_box()
        if bounds and bounds.is_valid:
            final_offset_x = -bounds.min_x   # shift so min_x → 0
            final_offset_y = bounds.max_y     # Y-flip anchor: new_y = max_y - old_y
            logger.debug(
                "DXF bounds: (%.1f, %.1f) – (%.1f, %.1f) mm  |  "
                "size: %.1f × %.1f mm",
                bounds.min_x, bounds.min_y, bounds.max_x, bounds.max_y,
                bounds.max_x - bounds.min_x, bounds.max_y - bounds.min_y,
            )
        else:
            final_offset_x = 0.0
            final_offset_y = 0.0

        has_commands = False

        for color in self._entities.get_colors():
            color_setting = settings.get(str(color), {})

            skip_value = color_setting.get("skip", False)
            logger.debug("Color %s: skip=%s", color, skip_value)

            if skip_value:
                logger.debug("Skipping color %s", color)
                continue

            entities = self._entities.get_by_color(color)
            if not entities:
                logger.debug("Color %s: no entities found", color)
                continue

            # Create and apply tool settings for this color
            tool = ToolSettings(
                toolholder=color_setting.get("tool", 1),
                force=color_setting.get("force", 10),
                speed=color_setting.get("speed", 5),
                depth=color_setting.get("depth", 3),
            )

            # Apply tool settings before this color's entities
            builder.apply_tool_settings(tool)

            tool_name = "PEN (Tool 2)" if tool.toolholder == 2 else "CUTTER (Tool 1)"
            logger.debug(
                "Color %s: %s  force=%d  speed=%d  depth=%d",
                color, tool_name, tool.force, tool.speed, tool.depth,
            )

            passes = color_setting.get("passes", 1)

            # Generate GPGL for each entity with normalized offset applied
            for entity in entities:
                for _ in range(passes):
                    cmds = entity.to_gpgl(
                        scale=1.0,
                        offset_x=final_offset_x,
                        offset_y=final_offset_y
                    )
                    for cmd in cmds:
                        builder.add(cmd)
                    has_commands = True

        if not has_commands:
            return None

        builder.home()

        # Calculate bounds for job
        bounds = self._entities.get_bounding_box()
        width_mm = bounds.max_x - bounds.min_x if bounds else 0
        height_mm = bounds.max_y - bounds.min_y if bounds else 0

        return CuttingJob(
            name=self._current_file.name if self._current_file else "Untitled",
            commands=builder.build(),
            width_mm=width_mm,
            height_mm=height_mm,
            entity_count=len(self._entities)
        )

    def _on_send(self):
        """Handle send button click"""
        job = self._create_job()
        if job:
            self.device_panel.set_job(job)
            self.device_panel._on_send_clicked()

    def _set_canvas_mode(self, mode: CanvasMode):
        """Set canvas interaction mode"""
        self.canvas.set_mode(mode)
        self.tool_mode_btn.setChecked(mode == CanvasMode.TOOL_POSITION)
        self.drag_mode_btn.setChecked(mode == CanvasMode.DESIGN_DRAG)

    def _on_tool_position_changed(self, x_mm: float, y_mm: float):
        """Handle tool position change - move device to new position

        Coordinates from canvas are already in Cameo coordinate system:
        - Origin at top-left
        - X increases to the right
        - Y increases downward

        These are converted to SU and sent as ABSOLUTE coordinates to the device.
        """
        if self.device_panel.is_connected:
            # Convert mm to SU (20 SU per mm)
            # These are ABSOLUTE coordinates from device home position (top-left)
            x_su = int(x_mm * 20)
            y_su = int(y_mm * 20)

            logger.debug("Canvas click: (%.1f, %.1f)mm → (%d, %d) SU", x_mm, y_mm, x_su, y_su)

            # Use pen (Tool 2) for position alignment
            toolholder = 2
            self.device_panel.move_to(x_su, y_su, toolholder)
            self.statusbar.showMessage(f"Moving pen to ({x_mm:.1f}, {y_mm:.1f})mm (absolute from home)", 2000)

    def _on_import_gpgl(self):
        """Import GPGL file"""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import GPGL File",
            "",
            "GPGL Files (*.gpgl);;All Files (*)"
        )

        if filepath:
            try:
                gpgl = GPGLFile.load(filepath)
                if gpgl:
                    # Show loaded commands info
                    readable = gpgl.get_human_readable()
                    lines = readable.split('\n')
                    preview = '\n'.join(lines[:10])
                    if len(lines) > 10:
                        preview += "\n..."

                    QMessageBox.information(
                        self,
                        "GPGL Imported",
                        f"Loaded {len(gpgl)} commands from {Path(filepath).name}\n\n"
                        f"Commands:\n{preview}"
                    )
                else:
                    QMessageBox.warning(self, "Warning", "Failed to load GPGL file")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import GPGL:\n{e}")

    def _on_export_gpgl(self):
        """Export current job to GPGL file"""
        if not self._entities:
            QMessageBox.warning(self, "Warning", "No design loaded to export")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export GPGL File",
            "",
            "GPGL Files (*.gpgl);;All Files (*)"
        )

        if filepath:
            if not filepath.endswith('.gpgl'):
                filepath += '.gpgl'

            try:
                # Generate commands
                commands = self._generate_gpgl_commands()
                if commands:
                    gpgl = GPGLFile()
                    for cmd in commands:
                        gpgl.add_command(cmd.encode('ascii') + b'\x03')

                    # Add metadata
                    gpgl.metadata["source_file"] = self._current_file.name if self._current_file else "CameoCut"
                    bounds = self._entities.get_bounding_box()
                    if bounds:
                        gpgl.metadata["width_mm"] = bounds.max_x - bounds.min_x
                        gpgl.metadata["height_mm"] = bounds.max_y - bounds.min_y
                    gpgl.metadata["entity_count"] = len(self._entities)

                    gpgl.save(filepath)
                    QMessageBox.information(
                        self,
                        "GPGL Exported",
                        f"Saved {len(commands)} commands to {Path(filepath).name}"
                    )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export GPGL:\n{e}")

    def _generate_gpgl_commands(self) -> list:
        """Generate GPGL command strings from current entities"""
        if not self._entities:
            return []

        commands = []
        settings = self.color_settings.get_all_settings()

        # Normalize coordinates to start from (0,0) with Y-flip
        bounds = self._entities.get_bounding_box()
        if bounds and bounds.is_valid:
            final_offset_x = -bounds.min_x
            final_offset_y = bounds.max_y  # For Y-flip
        else:
            final_offset_x = 0
            final_offset_y = 0

        # Setup commands
        commands.append("H")    # Home first
        commands.append("FN0")
        commands.append("SO0")

        for color in self._entities.get_colors():
            color_setting = settings.get(str(color), {})

            if color_setting.get("skip", False):
                continue

            # Tool selection
            tool = color_setting.get("tool", 1)
            commands.append(f"J{tool}")

            # Force and speed
            force = color_setting.get("force", 10)
            speed = color_setting.get("speed", 5)
            commands.append(f"!{force},{tool}")
            commands.append(f"FX{speed},{tool}")

            entities = self._entities.get_by_color(color)
            for entity in entities:
                gpgl_cmds = entity.to_gpgl(
                    scale=1.0,
                    offset_x=final_offset_x,
                    offset_y=final_offset_y
                )
                commands.extend(gpgl_cmds)

        commands.append("H")
        return commands

    # Drag and drop support
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith('.dxf'):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        """Handle drop"""
        urls = event.mimeData().urls()
        if urls:
            filepath = urls[0].toLocalFile()
            if filepath.lower().endswith('.dxf'):
                self._load_dxf(Path(filepath))

    def closeEvent(self, event):
        """Handle window close"""
        # Disconnect device if connected
        if self.device_panel.is_connected:
            self.device_panel._disconnect()

        event.accept()
