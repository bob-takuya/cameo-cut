"""
DXF Parser for CameoCut

Uses ezdxf library for fast and accurate DXF file parsing.
Extracts geometry and color information for cutting.
"""

import logging
import math
from pathlib import Path
from typing import Optional, List, Tuple

try:
    import ezdxf
    from ezdxf.entities import (
        Line, LWPolyline, Polyline, Circle, Arc, Ellipse, Spline
    )
    from ezdxf.math import Vec3
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False

from .entities import (
    EntityCollection, CuttingEntity,
    LineEntity, PolylineEntity, CircleEntity,
    ArcEntity, EllipseEntity, SplineEntity,
    BoundingBox
)

logger = logging.getLogger(__name__)


class DXFParseError(Exception):
    """Error parsing DXF file"""
    pass


class DXFParser:
    """Parser for DXF files"""

    def __init__(self):
        if not EZDXF_AVAILABLE:
            raise ImportError("ezdxf is not installed. Run: pip install ezdxf")

    def parse_file(self, filepath: str | Path) -> EntityCollection:
        """Parse a DXF file and extract cutting entities

        Args:
            filepath: Path to the DXF file

        Returns:
            EntityCollection containing all parsed entities

        Raises:
            DXFParseError: If file cannot be parsed
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise DXFParseError(f"File not found: {filepath}")

        if not filepath.suffix.lower() == '.dxf':
            raise DXFParseError(f"Not a DXF file: {filepath}")

        try:
            doc = ezdxf.readfile(str(filepath))
        except IOError as e:
            raise DXFParseError(f"Cannot read file: {e}")
        except ezdxf.DXFStructureError as e:
            raise DXFParseError(f"Invalid DXF structure: {e}")

        return self._parse_document(doc)

    def parse_bytes(self, data: bytes) -> EntityCollection:
        """Parse DXF data from bytes

        Args:
            data: DXF file content as bytes

        Returns:
            EntityCollection containing all parsed entities
        """
        try:
            doc = ezdxf.read(data)
        except Exception as e:
            raise DXFParseError(f"Cannot parse DXF data: {e}")

        return self._parse_document(doc)

    def _parse_document(self, doc: 'ezdxf.document.Drawing') -> EntityCollection:
        """Parse entities from an ezdxf document"""
        collection = EntityCollection()

        # Get units from header
        units = self._get_units(doc)
        scale = self._get_scale_factor(units)

        logger.info(f"DXF units: {units}, scale factor: {scale}")

        # Parse modelspace entities
        msp = doc.modelspace()

        for entity in msp:
            try:
                parsed = self._parse_entity(entity, doc, scale)
                if parsed:
                    collection.add(parsed)
            except Exception as e:
                logger.warning(f"Failed to parse entity {entity.dxftype()}: {e}")

        logger.info(f"Parsed {len(collection)} entities")
        return collection

    def _get_units(self, doc: 'ezdxf.document.Drawing') -> int:
        """Get DXF units from header"""
        try:
            return doc.header.get('$INSUNITS', 0)
        except Exception:
            return 0  # Unitless

    def _get_scale_factor(self, units: int) -> float:
        """Get scale factor to convert to millimeters"""
        # DXF unit codes
        UNITS_TO_MM = {
            0: 1.0,      # Unitless - assume mm
            1: 25.4,     # Inches
            2: 304.8,    # Feet
            4: 1.0,      # Millimeters
            5: 10.0,     # Centimeters
            6: 1000.0,   # Meters
        }
        return UNITS_TO_MM.get(units, 1.0)

    def _get_color(self, entity, doc: 'ezdxf.document.Drawing') -> int:
        """Get effective color of an entity"""
        color = entity.dxf.color

        if color == 256:  # BYLAYER
            try:
                layer = doc.layers.get(entity.dxf.layer)
                color = layer.color if layer else 7
            except Exception:
                color = 7
        elif color == 0:  # BYBLOCK
            color = 7  # Default to white

        return color

    def _get_layer(self, entity) -> str:
        """Get layer name of an entity"""
        try:
            return entity.dxf.layer
        except Exception:
            return "0"

    def _parse_entity(
        self,
        entity,
        doc: 'ezdxf.document.Drawing',
        scale: float
    ) -> Optional[CuttingEntity]:
        """Parse a single DXF entity"""
        entity_type = entity.dxftype()
        color = self._get_color(entity, doc)
        layer = self._get_layer(entity)

        if entity_type == 'LINE':
            return self._parse_line(entity, color, layer, scale)
        elif entity_type == 'LWPOLYLINE':
            return self._parse_lwpolyline(entity, color, layer, scale)
        elif entity_type == 'POLYLINE':
            return self._parse_polyline(entity, color, layer, scale)
        elif entity_type == 'CIRCLE':
            return self._parse_circle(entity, color, layer, scale)
        elif entity_type == 'ARC':
            return self._parse_arc(entity, color, layer, scale)
        elif entity_type == 'ELLIPSE':
            return self._parse_ellipse(entity, color, layer, scale)
        elif entity_type == 'SPLINE':
            return self._parse_spline(entity, color, layer, scale)

        # Unsupported entity type
        logger.debug(f"Skipping unsupported entity type: {entity_type}")
        return None

    def _parse_line(self, entity: 'Line', color: int, layer: str, scale: float) -> LineEntity:
        """Parse a LINE entity"""
        start = entity.dxf.start
        end = entity.dxf.end

        return LineEntity(
            start_x=start.x * scale,
            start_y=start.y * scale,
            end_x=end.x * scale,
            end_y=end.y * scale,
            color=color,
            layer=layer
        )

    def _parse_lwpolyline(
        self,
        entity: 'LWPolyline',
        color: int,
        layer: str,
        scale: float
    ) -> PolylineEntity:
        """Parse a LWPOLYLINE entity"""
        points = []

        for x, y, start_width, end_width, bulge in entity.get_points():
            points.append((x * scale, y * scale))

            # Handle bulge (arc segments)
            # For now, we just use straight segments
            # TODO: Convert bulge to arc segments

        return PolylineEntity(
            points=points,
            closed=entity.closed,
            color=color,
            layer=layer
        )

    def _parse_polyline(
        self,
        entity: 'Polyline',
        color: int,
        layer: str,
        scale: float
    ) -> PolylineEntity:
        """Parse a POLYLINE entity"""
        points = []

        for vertex in entity.vertices:
            point = vertex.dxf.location
            points.append((point.x * scale, point.y * scale))

        return PolylineEntity(
            points=points,
            closed=entity.is_closed,
            color=color,
            layer=layer
        )

    def _parse_circle(
        self,
        entity: 'Circle',
        color: int,
        layer: str,
        scale: float
    ) -> CircleEntity:
        """Parse a CIRCLE entity"""
        center = entity.dxf.center

        return CircleEntity(
            center_x=center.x * scale,
            center_y=center.y * scale,
            radius=entity.dxf.radius * scale,
            color=color,
            layer=layer
        )

    def _parse_arc(
        self,
        entity: 'Arc',
        color: int,
        layer: str,
        scale: float
    ) -> ArcEntity:
        """Parse an ARC entity"""
        center = entity.dxf.center

        return ArcEntity(
            center_x=center.x * scale,
            center_y=center.y * scale,
            radius=entity.dxf.radius * scale,
            start_angle=entity.dxf.start_angle,
            end_angle=entity.dxf.end_angle,
            color=color,
            layer=layer
        )

    def _parse_ellipse(
        self,
        entity: 'Ellipse',
        color: int,
        layer: str,
        scale: float
    ) -> EllipseEntity:
        """Parse an ELLIPSE entity"""
        center = entity.dxf.center
        major_axis = entity.dxf.major_axis

        # Calculate major axis length and rotation
        major_length = math.sqrt(
            major_axis.x**2 + major_axis.y**2 + major_axis.z**2
        ) * scale
        minor_length = major_length * entity.dxf.ratio
        rotation = math.degrees(math.atan2(major_axis.y, major_axis.x))

        # Convert parametric angles to degrees
        start_angle = math.degrees(entity.dxf.start_param)
        end_angle = math.degrees(entity.dxf.end_param)

        return EllipseEntity(
            center_x=center.x * scale,
            center_y=center.y * scale,
            major_axis=major_length,
            minor_axis=minor_length,
            rotation=rotation,
            start_angle=start_angle,
            end_angle=end_angle,
            color=color,
            layer=layer
        )

    def _parse_spline(
        self,
        entity: 'Spline',
        color: int,
        layer: str,
        scale: float
    ) -> SplineEntity:
        """Parse a SPLINE entity"""
        control_points = []

        for point in entity.control_points:
            control_points.append((point.x * scale, point.y * scale))

        return SplineEntity(
            control_points=control_points,
            degree=entity.dxf.degree,
            closed=entity.closed,
            color=color,
            layer=layer
        )


def parse_dxf(filepath: str | Path) -> EntityCollection:
    """Convenience function to parse a DXF file

    Args:
        filepath: Path to the DXF file

    Returns:
        EntityCollection containing all parsed entities
    """
    parser = DXFParser()
    return parser.parse_file(filepath)


def get_dxf_info(filepath: str | Path) -> dict:
    """Get basic information about a DXF file without full parsing

    Args:
        filepath: Path to the DXF file

    Returns:
        Dictionary with file info
    """
    if not EZDXF_AVAILABLE:
        raise ImportError("ezdxf is not installed")

    filepath = Path(filepath)

    try:
        doc = ezdxf.readfile(str(filepath))

        # Count entities by type
        entity_counts = {}
        msp = doc.modelspace()
        for entity in msp:
            etype = entity.dxftype()
            entity_counts[etype] = entity_counts.get(etype, 0) + 1

        # Get layer names
        layers = [layer.dxf.name for layer in doc.layers]

        return {
            'filename': filepath.name,
            'dxf_version': doc.dxfversion,
            'encoding': doc.encoding,
            'entity_counts': entity_counts,
            'total_entities': sum(entity_counts.values()),
            'layers': layers,
            'units': doc.header.get('$INSUNITS', 0),
        }

    except Exception as e:
        return {
            'filename': filepath.name,
            'error': str(e)
        }
