"""
DXF Entity abstraction for Silhouette cutting

Provides a unified interface for different DXF entity types,
mapping them to GPGL commands.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from enum import Enum, auto
import math


class EntityType(Enum):
    """Types of geometric entities"""
    LINE = auto()
    POLYLINE = auto()
    CIRCLE = auto()
    ARC = auto()
    ELLIPSE = auto()
    SPLINE = auto()


@dataclass
class BoundingBox:
    """Axis-aligned bounding box"""
    min_x: float = float('inf')
    min_y: float = float('inf')
    max_x: float = float('-inf')
    max_y: float = float('-inf')

    def expand(self, x: float, y: float) -> None:
        """Expand bounding box to include point"""
        self.min_x = min(self.min_x, x)
        self.min_y = min(self.min_y, y)
        self.max_x = max(self.max_x, x)
        self.max_y = max(self.max_y, y)

    def expand_box(self, other: 'BoundingBox') -> None:
        """Expand to include another bounding box"""
        if other.is_valid:
            self.expand(other.min_x, other.min_y)
            self.expand(other.max_x, other.max_y)

    @property
    def is_valid(self) -> bool:
        """Check if bounding box has been initialized"""
        return self.min_x != float('inf')

    @property
    def width(self) -> float:
        """Get width"""
        return self.max_x - self.min_x if self.is_valid else 0

    @property
    def height(self) -> float:
        """Get height"""
        return self.max_y - self.min_y if self.is_valid else 0

    @property
    def center(self) -> Tuple[float, float]:
        """Get center point"""
        return (
            (self.min_x + self.max_x) / 2,
            (self.min_y + self.max_y) / 2
        )


class CuttingEntity(ABC):
    """Abstract base class for cutting entities"""

    def __init__(self, color: int = 7, layer: str = "0"):
        self.color = color  # DXF color index
        self.layer = layer

    @property
    @abstractmethod
    def entity_type(self) -> EntityType:
        """Get entity type"""
        pass

    @abstractmethod
    def get_bounding_box(self) -> BoundingBox:
        """Calculate bounding box"""
        pass

    @abstractmethod
    def to_gpgl(self, scale: float = 1.0, offset_x: float = 0, offset_y: float = 0, flip_y: bool = True) -> List[str]:
        """Convert to GPGL commands

        Args:
            scale: Scale factor to apply
            offset_x: X offset in mm
            offset_y: Y offset in mm

        Returns:
            List of GPGL command strings
        """
        pass


@dataclass
class LineEntity(CuttingEntity):
    """A simple line segment"""
    start_x: float = 0
    start_y: float = 0
    end_x: float = 0
    end_y: float = 0
    color: int = 7
    layer: str = "0"

    @property
    def entity_type(self) -> EntityType:
        return EntityType.LINE

    def get_bounding_box(self) -> BoundingBox:
        bbox = BoundingBox()
        bbox.expand(self.start_x, self.start_y)
        bbox.expand(self.end_x, self.end_y)
        return bbox

    def to_gpgl(self, scale: float = 1.0, offset_x: float = 0, offset_y: float = 0, flip_y: bool = True) -> List[str]:
        from gpgl.protocol import mm_to_su

        # Apply X offset normally
        x1 = (self.start_x + offset_x) * scale
        x2 = (self.end_x + offset_x) * scale

        # Y-axis: if flip_y, offset_y is max_y and we subtract the coordinate
        if flip_y:
            y1 = (offset_y - self.start_y) * scale
            y2 = (offset_y - self.end_y) * scale
        else:
            y1 = (self.start_y + offset_y) * scale
            y2 = (self.end_y + offset_y) * scale

        # Convert to SU
        x1_su = mm_to_su(x1)
        y1_su = mm_to_su(y1)
        x2_su = mm_to_su(x2)
        y2_su = mm_to_su(y2)

        return [f"M{y1_su},{x1_su}", f"D{y2_su},{x2_su}"]


@dataclass
class PolylineEntity(CuttingEntity):
    """A polyline (multiple connected segments)"""
    points: List[Tuple[float, float]] = field(default_factory=list)
    closed: bool = False
    color: int = 7
    layer: str = "0"

    @property
    def entity_type(self) -> EntityType:
        return EntityType.POLYLINE

    def get_bounding_box(self) -> BoundingBox:
        bbox = BoundingBox()
        for x, y in self.points:
            bbox.expand(x, y)
        return bbox

    def to_gpgl(self, scale: float = 1.0, offset_x: float = 0, offset_y: float = 0, flip_y: bool = True) -> List[str]:
        from gpgl.protocol import mm_to_su

        if len(self.points) < 2:
            return []

        commands = []

        # Move to first point
        x, y = self.points[0]
        sx = (x + offset_x) * scale
        sy = ((offset_y - y) if flip_y else (y + offset_y)) * scale
        commands.append(f"M{mm_to_su(sy)},{mm_to_su(sx)}")

        # Draw to remaining points
        for x, y in self.points[1:]:
            sx = (x + offset_x) * scale
            sy = ((offset_y - y) if flip_y else (y + offset_y)) * scale
            commands.append(f"D{mm_to_su(sy)},{mm_to_su(sx)}")

        # Close if needed
        if self.closed and len(self.points) > 2:
            x, y = self.points[0]
            sx = (x + offset_x) * scale
            sy = ((offset_y - y) if flip_y else (y + offset_y)) * scale
            commands.append(f"D{mm_to_su(sy)},{mm_to_su(sx)}")

        return commands


@dataclass
class CircleEntity(CuttingEntity):
    """A circle - uses native GPGL W command"""
    center_x: float = 0
    center_y: float = 0
    radius: float = 0
    color: int = 7
    layer: str = "0"

    @property
    def entity_type(self) -> EntityType:
        return EntityType.CIRCLE

    def get_bounding_box(self) -> BoundingBox:
        bbox = BoundingBox()
        bbox.expand(self.center_x - self.radius, self.center_y - self.radius)
        bbox.expand(self.center_x + self.radius, self.center_y + self.radius)
        return bbox

    def to_gpgl(self, scale: float = 1.0, offset_x: float = 0, offset_y: float = 0, flip_y: bool = True) -> List[str]:
        from gpgl.protocol import mm_to_su

        cx = (self.center_x + offset_x) * scale
        cy = ((offset_y - self.center_y) if flip_y else (self.center_y + offset_y)) * scale
        r = self.radius * scale

        # Native GPGL circle command: W x,y,ra,rb,ta,tb
        return [f"W{mm_to_su(cx)},{mm_to_su(cy)},{mm_to_su(r)},{mm_to_su(r)},0,360"]


@dataclass
class ArcEntity(CuttingEntity):
    """An arc - uses native GPGL W command with angles"""
    center_x: float = 0
    center_y: float = 0
    radius: float = 0
    start_angle: float = 0  # degrees
    end_angle: float = 360  # degrees
    color: int = 7
    layer: str = "0"

    @property
    def entity_type(self) -> EntityType:
        return EntityType.ARC

    def get_bounding_box(self) -> BoundingBox:
        bbox = BoundingBox()
        # Simple approximation using the full circle bounds
        # More accurate would check which quadrants the arc passes through
        bbox.expand(self.center_x - self.radius, self.center_y - self.radius)
        bbox.expand(self.center_x + self.radius, self.center_y + self.radius)
        return bbox

    def to_gpgl(self, scale: float = 1.0, offset_x: float = 0, offset_y: float = 0, flip_y: bool = True) -> List[str]:
        from gpgl.protocol import mm_to_su

        cx = (self.center_x + offset_x) * scale
        cy = ((offset_y - self.center_y) if flip_y else (self.center_y + offset_y)) * scale
        r = self.radius * scale

        # When Y is flipped, angles are also flipped
        if flip_y:
            start_angle = 360 - self.end_angle
            end_angle = 360 - self.start_angle
        else:
            start_angle = self.start_angle
            end_angle = self.end_angle

        # Move to arc start first
        start_rad = math.radians(start_angle)
        cx_su = mm_to_su(cx)
        cy_su = mm_to_su(cy)
        r_su = mm_to_su(r)
        start_x = cx_su + int(r_su * math.cos(start_rad))
        start_y = cy_su + int(r_su * math.sin(start_rad))

        # Native GPGL arc command
        return [
            f"M{start_y},{start_x}",
            f"W{cx_su},{cy_su},{r_su},{r_su},{start_angle:.1f},{end_angle:.1f}"
        ]


@dataclass
class EllipseEntity(CuttingEntity):
    """An ellipse - uses native GPGL ) command"""
    center_x: float = 0
    center_y: float = 0
    major_axis: float = 0  # major axis length
    minor_axis: float = 0  # minor axis length
    rotation: float = 0  # rotation angle in degrees
    start_angle: float = 0  # degrees
    end_angle: float = 360  # degrees
    color: int = 7
    layer: str = "0"

    @property
    def entity_type(self) -> EntityType:
        return EntityType.ELLIPSE

    def get_bounding_box(self) -> BoundingBox:
        bbox = BoundingBox()
        # Simple approximation using larger axis
        r = max(self.major_axis, self.minor_axis)
        bbox.expand(self.center_x - r, self.center_y - r)
        bbox.expand(self.center_x + r, self.center_y + r)
        return bbox

    def to_gpgl(self, scale: float = 1.0, offset_x: float = 0, offset_y: float = 0, flip_y: bool = True) -> List[str]:
        from gpgl.protocol import mm_to_su

        cx = (self.center_x + offset_x) * scale
        cy = ((offset_y - self.center_y) if flip_y else (self.center_y + offset_y)) * scale

        ra = self.major_axis * scale
        rb = self.minor_axis * scale

        # When Y is flipped, angles and rotation are also affected
        if flip_y:
            start_angle = 360 - self.end_angle
            end_angle = 360 - self.start_angle
            rotation = -self.rotation
        else:
            start_angle = self.start_angle
            end_angle = self.end_angle
            rotation = self.rotation

        # Native GPGL ellipse command: )a,x,y,ra,rb,ta,tb,tc
        # a=0: move with pen up to start
        return [f")0,{mm_to_su(cx)},{mm_to_su(cy)},{mm_to_su(ra)},{mm_to_su(rb)},{start_angle:.1f},{end_angle:.1f},{rotation:.1f}"]


@dataclass
class SplineEntity(CuttingEntity):
    """A spline curve - uses native GPGL BZ/Y commands"""
    control_points: List[Tuple[float, float]] = field(default_factory=list)
    degree: int = 3
    closed: bool = False
    color: int = 7
    layer: str = "0"

    @property
    def entity_type(self) -> EntityType:
        return EntityType.SPLINE

    def get_bounding_box(self) -> BoundingBox:
        bbox = BoundingBox()
        for x, y in self.control_points:
            bbox.expand(x, y)
        return bbox

    def to_gpgl(self, scale: float = 1.0, offset_x: float = 0, offset_y: float = 0, flip_y: bool = True) -> List[str]:
        from gpgl.protocol import mm_to_su

        if len(self.control_points) < 2:
            return []

        commands = []

        # Convert points to SU
        su_points = []
        for x, y in self.control_points:
            sx = (x + offset_x) * scale
            sy = ((offset_y - y) if flip_y else (y + offset_y)) * scale
            su_points.append((mm_to_su(sx), mm_to_su(sy)))

        # For cubic splines with 4+ control points, use BZ command
        if self.degree == 3 and len(su_points) >= 4:
            # Process in groups of 4 points
            for i in range(0, len(su_points) - 3, 3):
                p0 = su_points[i]
                p1 = su_points[i + 1]
                p2 = su_points[i + 2]
                p3 = su_points[i + 3]
                commands.append(
                    f"BZ0,{p0[0]},{p0[1]},{p1[0]},{p1[1]},"
                    f"{p2[0]},{p2[1]},{p3[0]},{p3[1]}"
                )
        else:
            # Use Y command for general curves
            a = 1 if self.closed else 0
            coords = ",".join(f"{p[0]},{p[1]}" for p in su_points)
            commands.append(f"Y{a},{coords}")

        return commands


@dataclass
class EntityCollection:
    """Collection of cutting entities grouped by color"""
    entities: List[CuttingEntity] = field(default_factory=list)

    def add(self, entity: CuttingEntity) -> None:
        """Add an entity to the collection"""
        self.entities.append(entity)

    def get_by_color(self, color: int) -> List[CuttingEntity]:
        """Get all entities with a specific color"""
        return [e for e in self.entities if e.color == color]

    def get_colors(self) -> List[int]:
        """Get list of unique colors used"""
        return sorted(set(e.color for e in self.entities))

    def get_color_counts(self) -> dict[int, int]:
        """Get count of entities per color"""
        counts = {}
        for entity in self.entities:
            counts[entity.color] = counts.get(entity.color, 0) + 1
        return counts

    def get_bounding_box(self) -> BoundingBox:
        """Get bounding box of all entities"""
        bbox = BoundingBox()
        for entity in self.entities:
            bbox.expand_box(entity.get_bounding_box())
        return bbox

    def to_gpgl(
        self,
        color_order: Optional[List[int]] = None,
        scale: float = 1.0,
        offset_x: float = 0,
        offset_y: float = 0
    ) -> List[str]:
        """Convert all entities to GPGL commands

        Args:
            color_order: Order to process colors (None = natural order)
            scale: Scale factor
            offset_x: X offset in mm
            offset_y: Y offset in mm

        Returns:
            List of GPGL command strings
        """
        commands = []

        if color_order is None:
            color_order = self.get_colors()

        for color in color_order:
            for entity in self.get_by_color(color):
                commands.extend(entity.to_gpgl(scale, offset_x, offset_y))

        return commands

    def __len__(self) -> int:
        return len(self.entities)
