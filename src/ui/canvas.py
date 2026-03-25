"""
DXF Preview Canvas for CameoCut

Provides a fast 2D preview of DXF files using QPainter.
Fixed width display with vertical scroll only.
Click to move tool position for alignment.
Origin is at top-left (matching Cameo coordinate system).
"""

from typing import Optional, Dict, List
from enum import Enum
import math

from PyQt6.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QFrame
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QSize
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QBrush,
    QMouseEvent, QPainterPath
)

from dxf.entities import (
    EntityCollection, CuttingEntity, EntityType,
    LineEntity, PolylineEntity, CircleEntity,
    ArcEntity, EllipseEntity, SplineEntity, BoundingBox
)


# DXF color index to QColor mapping
DXF_COLORS: Dict[int, QColor] = {
    0: QColor(0, 0, 0),        # Black
    1: QColor(255, 0, 0),      # Red
    2: QColor(255, 255, 0),    # Yellow
    3: QColor(0, 255, 0),      # Green
    4: QColor(0, 255, 255),    # Cyan
    5: QColor(0, 0, 255),      # Blue
    6: QColor(255, 0, 255),    # Magenta
    7: QColor(255, 255, 255),  # White
    8: QColor(128, 128, 128),  # Dark Gray
    9: QColor(192, 192, 192),  # Light Gray
}


class CanvasMode(Enum):
    """Canvas interaction mode"""
    TOOL_POSITION = "tool"   # Click to set tool position
    DESIGN_DRAG = "drag"     # Drag to move design


class DXFCanvasInner(QWidget):
    """Inner canvas widget that draws the content"""

    # Signals
    tool_position_changed = pyqtSignal(float, float)  # x_mm, y_mm
    design_offset_changed = pyqtSignal(float, float)  # x_mm, y_mm
    mode_changed = pyqtSignal(str)  # mode name

    # Cameo 5 cutting area presets (in mm)
    CUTTING_AREAS = {
        "12x12": (304.8, 304.8),      # 12" x 12"
        "12x24": (304.8, 609.6),      # 12" x 24"
        "A4": (210.0, 297.0),         # A4
        "Letter": (215.9, 279.4),     # US Letter
        "A3": (297.0, 420.0),         # A3
        "Custom": (304.8, 304.8),     # Default custom
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entities: Optional[EntityCollection] = None
        self._scale = 1.0  # pixels per mm
        self._background_color = QColor(40, 40, 40)
        self._grid_color = QColor(60, 60, 60)
        self._show_grid = True
        self._grid_size_mm = 10.0  # Grid spacing in mm

        # Cutting area settings
        self._cutting_area_name = "12x12"
        self._cutting_area_width = 304.8  # mm
        self._cutting_area_height = 304.8  # mm
        self._show_cutting_area = True

        # Design offset (for positioning within cutting area)
        self._design_offset_x = 0.0  # mm
        self._design_offset_y = 0.0  # mm

        # Tool position (for alignment) - origin at top-left
        self._tool_pos_x = 0.0  # mm
        self._tool_pos_y = 0.0  # mm
        self._show_tool_position = True

        # Interaction mode
        self._mode = CanvasMode.TOOL_POSITION

        # Dragging state
        self._is_dragging = False
        self._last_mouse_pos = QPointF()

        # Margin for labels
        self._margin = 30  # pixels

        self.setMouseTracking(True)

    def set_mode(self, mode: CanvasMode):
        """Set interaction mode"""
        self._mode = mode
        self.mode_changed.emit(mode.value)
        if mode == CanvasMode.TOOL_POSITION:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.update()

    def get_mode(self) -> CanvasMode:
        """Get current interaction mode"""
        return self._mode

    def set_entities(self, entities: EntityCollection):
        """Set the entities to display"""
        self._entities = entities
        self._update_size()
        self.update()

    def clear(self):
        """Clear all entities"""
        self._entities = None
        self.update()

    def _update_size(self):
        """Update widget size based on cutting area and scale"""
        width = int(self._cutting_area_width * self._scale) + self._margin * 2
        height = int(self._cutting_area_height * self._scale) + self._margin * 2
        self.setMinimumSize(width, height)
        self.setFixedHeight(height)

    def update_scale(self, available_width: int):
        """Update scale to fit available width"""
        if available_width <= self._margin * 2:
            return
        self._scale = (available_width - self._margin * 2) / self._cutting_area_width
        self._update_size()
        self.update()

    def paintEvent(self, event):
        """Paint the canvas"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), self._background_color)

        # Cutting area (red border)
        if self._show_cutting_area:
            self._draw_cutting_area(painter)

        # Grid
        if self._show_grid:
            self._draw_grid(painter)

        # Entities
        if self._entities:
            self._draw_entities(painter)

        # Tool position crosshair
        if self._show_tool_position:
            self._draw_tool_position(painter)

        # Mode indicator
        self._draw_mode_indicator(painter)

    def _draw_cutting_area(self, painter: QPainter):
        """Draw the cutting area as a red border"""
        pen = QPen(QColor(255, 60, 60), 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))

        # Transform cutting area corners (origin at top-left, no Y flip)
        top_left = self._transform_point(0, 0, apply_offset=False, flip_y=False)
        bottom_right = self._transform_point(self._cutting_area_width, self._cutting_area_height, apply_offset=False, flip_y=False)

        rect = QRectF(top_left, bottom_right)
        painter.drawRect(rect)

        # Draw size label at top-left
        painter.setPen(QColor(255, 60, 60))
        label = f"{self._cutting_area_name} ({self._cutting_area_width:.0f}×{self._cutting_area_height:.0f}mm)"
        painter.drawText(int(top_left.x() + 5), int(top_left.y() - 5), label)

        # Draw offset info if non-zero
        if self._design_offset_x != 0 or self._design_offset_y != 0:
            offset_label = f"Design offset: ({self._design_offset_x:.1f}, {self._design_offset_y:.1f})mm"
            painter.drawText(int(top_left.x() + 5), int(bottom_right.y() + 15), offset_label)

    def _draw_tool_position(self, painter: QPainter):
        """Draw tool position crosshair and coordinates"""
        pos = self._transform_point(self._tool_pos_x, self._tool_pos_y, apply_offset=False, flip_y=False)

        # Crosshair color based on mode
        if self._mode == CanvasMode.TOOL_POSITION:
            color = QColor(0, 255, 0)  # Green when active
        else:
            color = QColor(0, 180, 0)  # Darker when not active

        pen = QPen(color, 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        # Vertical line
        painter.drawLine(int(pos.x()), int(pos.y() - 15), int(pos.x()), int(pos.y() + 15))
        # Horizontal line
        painter.drawLine(int(pos.x() - 15), int(pos.y()), int(pos.x() + 15), int(pos.y()))
        # Circle
        painter.drawEllipse(pos, 8, 8)

        # Position label
        label = f"Tool: ({self._tool_pos_x:.1f}, {self._tool_pos_y:.1f})mm"
        painter.setPen(color)
        painter.drawText(int(pos.x() + 12), int(pos.y() - 5), label)

    def _draw_mode_indicator(self, painter: QPainter):
        """Draw current mode indicator"""
        if self._mode == CanvasMode.TOOL_POSITION:
            text = "Mode: Tool Position (click to move)"
            color = QColor(0, 255, 0)
        else:
            text = "Mode: Design Drag (drag to move design)"
            color = QColor(255, 200, 0)

        painter.setPen(color)
        painter.drawText(self._margin, self.height() - 10, text)

    def _draw_grid(self, painter: QPainter):
        """Draw the background grid"""
        pen = QPen(self._grid_color, 1, Qt.PenStyle.DotLine)
        painter.setPen(pen)

        grid_size = self._grid_size_mm * self._scale

        if grid_size < 5:
            return  # Grid too dense

        # Draw grid lines within cutting area
        start_x = self._margin
        start_y = self._margin

        # Vertical lines
        x = start_x
        while x <= start_x + self._cutting_area_width * self._scale:
            painter.drawLine(int(x), int(start_y), int(x), int(start_y + self._cutting_area_height * self._scale))
            x += grid_size

        # Horizontal lines
        y = start_y
        while y <= start_y + self._cutting_area_height * self._scale:
            painter.drawLine(int(start_x), int(y), int(start_x + self._cutting_area_width * self._scale), int(y))
            y += grid_size

    def _draw_entities(self, painter: QPainter):
        """Draw all entities"""
        for entity in self._entities.entities:
            color = DXF_COLORS.get(entity.color, QColor(200, 200, 200))
            pen = QPen(color, 2)
            painter.setPen(pen)

            if isinstance(entity, LineEntity):
                self._draw_line(painter, entity)
            elif isinstance(entity, PolylineEntity):
                self._draw_polyline(painter, entity)
            elif isinstance(entity, CircleEntity):
                self._draw_circle(painter, entity)
            elif isinstance(entity, ArcEntity):
                self._draw_arc(painter, entity)
            elif isinstance(entity, EllipseEntity):
                self._draw_ellipse(painter, entity)
            elif isinstance(entity, SplineEntity):
                self._draw_spline(painter, entity)

    def _transform_point(self, x: float, y: float, apply_offset: bool = True, flip_y: bool = True) -> QPointF:
        """Transform a point from design coordinates to screen coordinates

        Origin is at top-left, Y increases downward (Cameo coordinate system).
        DXF coordinates have Y increasing upward, so we flip Y for DXF entities.

        Args:
            x: X coordinate in mm
            y: Y coordinate in mm
            apply_offset: Whether to apply design offset (False for cutting area)
            flip_y: Whether to flip Y axis (True for DXF entities, False for tool/cutting area)
        """
        if apply_offset:
            x = x + self._design_offset_x
            y = y + self._design_offset_y

        if flip_y:
            # DXF Y-up to screen Y-down: flip within cutting area
            y = self._cutting_area_height - y

        return QPointF(
            x * self._scale + self._margin,
            y * self._scale + self._margin
        )

    def _screen_to_design(self, screen_x: float, screen_y: float) -> tuple:
        """Convert screen coordinates to design coordinates (mm)"""
        x_mm = (screen_x - self._margin) / self._scale
        y_mm = (screen_y - self._margin) / self._scale
        return (x_mm, y_mm)

    def _draw_line(self, painter: QPainter, entity: LineEntity):
        """Draw a line"""
        p1 = self._transform_point(entity.start_x, entity.start_y)
        p2 = self._transform_point(entity.end_x, entity.end_y)
        painter.drawLine(p1, p2)

    def _draw_polyline(self, painter: QPainter, entity: PolylineEntity):
        """Draw a polyline"""
        if len(entity.points) < 2:
            return

        path = QPainterPath()
        first = self._transform_point(*entity.points[0])
        path.moveTo(first)

        for point in entity.points[1:]:
            p = self._transform_point(*point)
            path.lineTo(p)

        if entity.closed:
            path.closeSubpath()

        painter.drawPath(path)

    def _draw_circle(self, painter: QPainter, entity: CircleEntity):
        """Draw a circle"""
        center = self._transform_point(entity.center_x, entity.center_y)
        radius = entity.radius * self._scale
        painter.drawEllipse(center, radius, radius)

    def _draw_arc(self, painter: QPainter, entity: ArcEntity):
        """Draw an arc"""
        center = self._transform_point(entity.center_x, entity.center_y)
        radius = entity.radius * self._scale

        rect = QRectF(
            center.x() - radius,
            center.y() - radius,
            radius * 2,
            radius * 2
        )

        # Qt uses 1/16th of a degree, counterclockwise from 3 o'clock
        # With Y-down coordinate system, we need to negate angles
        start_angle = int(-entity.start_angle * 16)
        span_angle = int(-(entity.end_angle - entity.start_angle) * 16)

        painter.drawArc(rect, start_angle, span_angle)

    def _draw_ellipse(self, painter: QPainter, entity: EllipseEntity):
        """Draw an ellipse"""
        center = self._transform_point(entity.center_x, entity.center_y)
        major = entity.major_axis * self._scale
        minor = entity.minor_axis * self._scale

        painter.save()
        painter.translate(center)
        painter.rotate(entity.rotation)  # Positive rotation for Y-down

        rect = QRectF(-major, -minor, major * 2, minor * 2)

        if entity.start_angle == 0 and entity.end_angle >= 359:
            painter.drawEllipse(rect)
        else:
            start_angle = int(-entity.start_angle * 16)
            span_angle = int(-(entity.end_angle - entity.start_angle) * 16)
            painter.drawArc(rect, start_angle, span_angle)

        painter.restore()

    def _draw_spline(self, painter: QPainter, entity: SplineEntity):
        """Draw a spline (approximate with line segments)"""
        if len(entity.control_points) < 2:
            return

        path = QPainterPath()
        first = self._transform_point(*entity.control_points[0])
        path.moveTo(first)

        for point in entity.control_points[1:]:
            p = self._transform_point(*point)
            path.lineTo(p)

        if entity.closed:
            path.closeSubpath()

        painter.drawPath(path)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press"""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            x_mm, y_mm = self._screen_to_design(pos.x(), pos.y())

            # Check if within cutting area
            if 0 <= x_mm <= self._cutting_area_width and 0 <= y_mm <= self._cutting_area_height:
                if self._mode == CanvasMode.TOOL_POSITION:
                    # Move tool position
                    self._tool_pos_x = max(0, min(x_mm, self._cutting_area_width))
                    self._tool_pos_y = max(0, min(y_mm, self._cutting_area_height))
                    self.tool_position_changed.emit(self._tool_pos_x, self._tool_pos_y)
                    self.update()
                else:
                    # Start dragging design
                    self._is_dragging = True
                    self._last_mouse_pos = pos
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for dragging design"""
        if self._is_dragging and self._mode == CanvasMode.DESIGN_DRAG:
            delta = event.position() - self._last_mouse_pos
            delta_x_mm = delta.x() / self._scale
            # DXF Y is flipped, so negate the delta
            delta_y_mm = -delta.y() / self._scale

            self._design_offset_x += delta_x_mm
            self._design_offset_y += delta_y_mm
            self._last_mouse_pos = event.position()

            self.design_offset_changed.emit(self._design_offset_x, self._design_offset_y)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release"""
        if self._is_dragging:
            self._is_dragging = False
            if self._mode == CanvasMode.DESIGN_DRAG:
                self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_tool_position(self, x_mm: float, y_mm: float):
        """Set tool position programmatically"""
        self._tool_pos_x = x_mm
        self._tool_pos_y = y_mm
        self.update()

    def get_tool_position(self) -> tuple:
        """Get current tool position (x_mm, y_mm)"""
        return (self._tool_pos_x, self._tool_pos_y)

    def set_cutting_area(self, name: str, width_mm: float = None, height_mm: float = None):
        """Set the cutting area size"""
        self._cutting_area_name = name
        if name in self.CUTTING_AREAS:
            self._cutting_area_width, self._cutting_area_height = self.CUTTING_AREAS[name]
        elif width_mm and height_mm:
            self._cutting_area_width = width_mm
            self._cutting_area_height = height_mm
        self._update_size()
        self.update()

    def get_cutting_area(self) -> tuple:
        """Get current cutting area (name, width_mm, height_mm)"""
        return (self._cutting_area_name, self._cutting_area_width, self._cutting_area_height)

    def set_design_offset(self, x_mm: float, y_mm: float):
        """Set the design offset within the cutting area"""
        self._design_offset_x = x_mm
        self._design_offset_y = y_mm
        self.design_offset_changed.emit(x_mm, y_mm)
        self.update()

    def get_design_offset(self) -> tuple:
        """Get current design offset (x_mm, y_mm)"""
        return (self._design_offset_x, self._design_offset_y)

    def set_show_grid(self, show: bool):
        """Show or hide the grid"""
        self._show_grid = show
        self.update()

    def set_show_cutting_area(self, show: bool):
        """Show or hide the cutting area border"""
        self._show_cutting_area = show
        self.update()

    def set_show_tool_position(self, show: bool):
        """Show or hide tool position"""
        self._show_tool_position = show
        self.update()


class DXFCanvas(QScrollArea):
    """Scrollable canvas wrapper for DXF display"""

    # Forward signals from inner canvas
    tool_position_changed = pyqtSignal(float, float)
    design_offset_changed = pyqtSignal(float, float)
    mode_changed = pyqtSignal(str)
    zoom_changed = pyqtSignal(float)  # Keep for compatibility (always 1.0)

    # Forward CUTTING_AREAS for compatibility
    CUTTING_AREAS = DXFCanvasInner.CUTTING_AREAS

    def __init__(self, parent=None):
        super().__init__(parent)

        # Create inner canvas
        self._inner = DXFCanvasInner()
        self.setWidget(self._inner)
        self.setWidgetResizable(False)

        # Scroll settings - vertical only
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Style
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background-color: #282828;")

        # Connect signals
        self._inner.tool_position_changed.connect(self.tool_position_changed.emit)
        self._inner.design_offset_changed.connect(self.design_offset_changed.emit)
        self._inner.mode_changed.connect(self.mode_changed.emit)

    def resizeEvent(self, event):
        """Handle resize to update scale"""
        super().resizeEvent(event)
        # Update inner canvas scale to fit width
        available_width = self.viewport().width()
        self._inner.update_scale(available_width)

    def set_entities(self, entities: EntityCollection):
        """Set the entities to display"""
        self._inner.set_entities(entities)

    def clear(self):
        """Clear all entities"""
        self._inner.clear()

    def fit_to_view(self):
        """Scroll to top (fit to view equivalent)"""
        self.verticalScrollBar().setValue(0)

    def set_zoom(self, zoom: float):
        """No-op for compatibility"""
        pass

    def get_zoom(self) -> float:
        """Return 1.0 for compatibility"""
        return 1.0

    def set_show_grid(self, show: bool):
        """Show or hide the grid"""
        self._inner.set_show_grid(show)

    def set_cutting_area(self, name: str, width_mm: float = None, height_mm: float = None):
        """Set the cutting area size"""
        self._inner.set_cutting_area(name, width_mm, height_mm)
        # Update scale after changing cutting area
        available_width = self.viewport().width()
        self._inner.update_scale(available_width)

    def get_cutting_area(self) -> tuple:
        """Get current cutting area (name, width_mm, height_mm)"""
        return self._inner.get_cutting_area()

    def set_show_cutting_area(self, show: bool):
        """Show or hide the cutting area border"""
        self._inner.set_show_cutting_area(show)

    def set_design_offset(self, x_mm: float, y_mm: float):
        """Set the design offset within the cutting area"""
        self._inner.set_design_offset(x_mm, y_mm)

    def get_design_offset(self) -> tuple:
        """Get current design offset (x_mm, y_mm)"""
        return self._inner.get_design_offset()

    def set_tool_position(self, x_mm: float, y_mm: float):
        """Set tool position"""
        self._inner.set_tool_position(x_mm, y_mm)

    def get_tool_position(self) -> tuple:
        """Get current tool position (x_mm, y_mm)"""
        return self._inner.get_tool_position()

    def set_show_tool_position(self, show: bool):
        """Show or hide tool position"""
        self._inner.set_show_tool_position(show)

    def set_mode(self, mode: CanvasMode):
        """Set interaction mode"""
        self._inner.set_mode(mode)

    def get_mode(self) -> CanvasMode:
        """Get current interaction mode"""
        return self._inner.get_mode()
