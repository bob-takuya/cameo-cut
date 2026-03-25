"""
GPGL Native Curve Commands for Silhouette Cameo

This module provides native GPGL curve commands without requiring
line segment approximation. GPGL supports:
- Circles (W command)
- Arcs (W command with angles)
- Ellipses () command)
- Bezier curves (BZ command)
- Cubic curves through points (Y command)
"""

import math
from typing import List, Tuple

from .protocol import mm_to_su


class GPGLCurveBuilder:
    """Builder for GPGL curve commands"""

    def __init__(self):
        self._commands: List[str] = []

    def add(self, command: str) -> 'GPGLCurveBuilder':
        """Add a command to the sequence"""
        self._commands.append(command)
        return self

    def get_commands(self) -> List[str]:
        """Get the list of commands"""
        return self._commands

    def clear(self) -> 'GPGLCurveBuilder':
        """Clear all commands"""
        self._commands.clear()
        return self

    # === Circle Commands (W) ===

    def circle(
        self,
        center_x: int,
        center_y: int,
        radius: int,
        segments: int | None = None
    ) -> 'GPGLCurveBuilder':
        """Draw a full circle

        GPGL W command: Wx,y,ra,rb,ta,tb[,d]
        - x,y: center coordinates
        - ra,rb: start and end radius (same for circle)
        - ta,tb: start and end angle (0-360 for full circle)
        - d: optional segment control

        Args:
            center_x: Center X coordinate in SU
            center_y: Center Y coordinate in SU
            radius: Circle radius in SU
            segments: Optional number of segments (negative value)
        """
        cmd = f"W{center_x},{center_y},{radius},{radius},0,360"
        if segments is not None:
            cmd += f",{-abs(segments)}"
        return self.add(cmd)

    def circle_mm(
        self,
        center_x: float,
        center_y: float,
        radius: float,
        segments: int | None = None
    ) -> 'GPGLCurveBuilder':
        """Draw a circle using millimeter coordinates"""
        return self.circle(
            mm_to_su(center_x),
            mm_to_su(center_y),
            mm_to_su(radius),
            segments
        )

    # === Arc Commands (W with angles) ===

    def arc(
        self,
        center_x: int,
        center_y: int,
        radius: int,
        start_angle: float,
        end_angle: float,
        segments: int | None = None
    ) -> 'GPGLCurveBuilder':
        """Draw an arc

        Args:
            center_x: Center X coordinate in SU
            center_y: Center Y coordinate in SU
            radius: Arc radius in SU
            start_angle: Start angle in degrees
            end_angle: End angle in degrees
            segments: Optional number of segments
        """
        # Normalize angles to 0-360 range
        start_angle = start_angle % 360
        end_angle = end_angle % 360

        cmd = f"W{center_x},{center_y},{radius},{radius},{start_angle:.1f},{end_angle:.1f}"
        if segments is not None:
            cmd += f",{-abs(segments)}"
        return self.add(cmd)

    def arc_mm(
        self,
        center_x: float,
        center_y: float,
        radius: float,
        start_angle: float,
        end_angle: float,
        segments: int | None = None
    ) -> 'GPGLCurveBuilder':
        """Draw an arc using millimeter coordinates"""
        return self.arc(
            mm_to_su(center_x),
            mm_to_su(center_y),
            mm_to_su(radius),
            start_angle,
            end_angle,
            segments
        )

    def arc_3point(
        self,
        x1: int, y1: int,
        x2: int, y2: int,
        x3: int, y3: int,
        segments: int | None = None
    ) -> 'GPGLCurveBuilder':
        """Draw an arc through 3 points (WP command)

        Args:
            x1, y1: First point
            x2, y2: Second point (on arc)
            x3, y3: Third point
            segments: Optional number of segments
        """
        cmd = f"WP{x1},{y1},{x2},{y2},{x3},{y3}"
        if segments is not None:
            cmd += f",{-abs(segments)}"
        return self.add(cmd)

    # === Ellipse Commands ()) ===

    def ellipse(
        self,
        center_x: int,
        center_y: int,
        major_axis: int,
        minor_axis: int,
        start_angle: float = 0,
        end_angle: float = 360,
        rotation: float = 0,
        pen_down_move: bool = False
    ) -> 'GPGLCurveBuilder':
        """Draw an ellipse

        GPGL ) command: )a,x,y,ra,rb,ta,tb,tc
        - a: 0=move with pen up to start, 1=move with pen down
        - x,y: center coordinates
        - ra,rb: major and minor axes
        - ta,tb: start and end angles
        - tc: rotation angle (angle between major axis and X axis)

        Args:
            center_x: Center X coordinate in SU
            center_y: Center Y coordinate in SU
            major_axis: Major axis length in SU
            minor_axis: Minor axis length in SU
            start_angle: Start angle in degrees
            end_angle: End angle in degrees
            rotation: Rotation angle in degrees
            pen_down_move: If True, move to start with pen down
        """
        a = 1 if pen_down_move else 0
        return self.add(
            f"){a},{center_x},{center_y},{major_axis},{minor_axis},"
            f"{start_angle:.1f},{end_angle:.1f},{rotation:.1f}"
        )

    def ellipse_mm(
        self,
        center_x: float,
        center_y: float,
        major_axis: float,
        minor_axis: float,
        start_angle: float = 0,
        end_angle: float = 360,
        rotation: float = 0,
        pen_down_move: bool = False
    ) -> 'GPGLCurveBuilder':
        """Draw an ellipse using millimeter coordinates"""
        return self.ellipse(
            mm_to_su(center_x),
            mm_to_su(center_y),
            mm_to_su(major_axis),
            mm_to_su(minor_axis),
            start_angle,
            end_angle,
            rotation,
            pen_down_move
        )

    # === Bezier Curve Commands (BZ) ===

    def bezier(
        self,
        p0: Tuple[int, int],
        p1: Tuple[int, int],
        p2: Tuple[int, int],
        p3: Tuple[int, int]
    ) -> 'GPGLCurveBuilder':
        """Draw a cubic Bezier curve

        GPGL BZ command: BZa,xa,ya,xb,yb,xc,yc,xd,yd[,d]
        - 4 control points define the cubic Bezier curve

        Args:
            p0: Start point (x, y) in SU
            p1: First control point (x, y) in SU
            p2: Second control point (x, y) in SU
            p3: End point (x, y) in SU
        """
        return self.add(
            f"BZ0,{p0[0]},{p0[1]},{p1[0]},{p1[1]},"
            f"{p2[0]},{p2[1]},{p3[0]},{p3[1]}"
        )

    def bezier_mm(
        self,
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        p3: Tuple[float, float]
    ) -> 'GPGLCurveBuilder':
        """Draw a cubic Bezier curve using millimeter coordinates"""
        return self.bezier(
            (mm_to_su(p0[0]), mm_to_su(p0[1])),
            (mm_to_su(p1[0]), mm_to_su(p1[1])),
            (mm_to_su(p2[0]), mm_to_su(p2[1])),
            (mm_to_su(p3[0]), mm_to_su(p3[1]))
        )

    def bezier_chain(
        self,
        control_points: List[Tuple[int, int]]
    ) -> 'GPGLCurveBuilder':
        """Draw a chain of connected cubic Bezier curves

        Args:
            control_points: List of control points. Must be 3n+1 points
                           where n is the number of Bezier segments.
                           Points: [start, ctrl1, ctrl2, end1/start2, ctrl3, ctrl4, end2, ...]
        """
        n_points = len(control_points)
        if n_points < 4:
            raise ValueError("Need at least 4 points for a Bezier curve")

        # Each Bezier segment needs 4 points, overlapping at endpoints
        # So for n segments: 3n + 1 points
        n_segments = (n_points - 1) // 3
        if (n_points - 1) % 3 != 0:
            raise ValueError(f"Invalid number of points: {n_points}. Need 3n+1 points.")

        for i in range(n_segments):
            idx = i * 3
            self.bezier(
                control_points[idx],
                control_points[idx + 1],
                control_points[idx + 2],
                control_points[idx + 3]
            )

        return self

    # === Cubic Curve Through Points (Y) ===

    def cubic_curve(
        self,
        points: List[Tuple[int, int]],
        closed: bool = False
    ) -> 'GPGLCurveBuilder':
        """Draw a smooth cubic curve through given points

        GPGL Y command: Ya,xa,ya,xb,yb,...xn,yn
        - a: 0=open curve, 1=closed curve
        - Points the curve passes through

        Args:
            points: List of points (x, y) in SU
            closed: If True, create a closed curve
        """
        if len(points) < 2:
            raise ValueError("Need at least 2 points for a curve")

        a = 1 if closed else 0
        coords = ",".join(f"{p[0]},{p[1]}" for p in points)
        return self.add(f"Y{a},{coords}")

    def cubic_curve_mm(
        self,
        points: List[Tuple[float, float]],
        closed: bool = False
    ) -> 'GPGLCurveBuilder':
        """Draw a smooth cubic curve using millimeter coordinates"""
        su_points = [(mm_to_su(p[0]), mm_to_su(p[1])) for p in points]
        return self.cubic_curve(su_points, closed)

    # === Relative Circle (]) ===

    def relative_circle(
        self,
        radius: int,
        start_angle: float = 0,
        end_angle: float = 360,
        segments: int | None = None
    ) -> 'GPGLCurveBuilder':
        """Draw a circle centered at current position

        GPGL ] command: ]ra,rb,ta,tb[,d]
        Like circle but centered at current pen position

        Args:
            radius: Circle radius in SU
            start_angle: Start angle in degrees
            end_angle: End angle in degrees
            segments: Optional number of segments
        """
        cmd = f"]{radius},{radius},{start_angle:.1f},{end_angle:.1f}"
        if segments is not None:
            cmd += f",{-abs(segments)}"
        return self.add(cmd)

    # === Relative Curve (_) ===

    def relative_curve(
        self,
        deltas: List[Tuple[int, int]],
        closed: bool = False
    ) -> 'GPGLCurveBuilder':
        """Draw a curve using relative coordinates

        GPGL _ command: _a,xa,ya,xb,yb,...xn,yn
        Like cubic_curve but uses delta coordinates from current position

        Args:
            deltas: List of delta coordinates (dx, dy) in SU
            closed: If True, create a closed curve
        """
        if len(deltas) < 2:
            raise ValueError("Need at least 2 points for a curve")

        a = 1 if closed else 0
        coords = ",".join(f"{d[0]},{d[1]}" for d in deltas)
        return self.add(f"_{a},{coords}")


# === Utility Functions ===

def dxf_arc_to_gpgl(
    center_x: float,
    center_y: float,
    radius: float,
    start_angle: float,
    end_angle: float
) -> str:
    """Convert DXF arc parameters to GPGL W command

    DXF arcs are counterclockwise from start to end angle.
    GPGL also uses counterclockwise direction.

    Args:
        center_x: Center X in mm
        center_y: Center Y in mm
        radius: Radius in mm
        start_angle: Start angle in degrees
        end_angle: End angle in degrees

    Returns:
        GPGL W command string
    """
    builder = GPGLCurveBuilder()
    builder.arc_mm(center_x, center_y, radius, start_angle, end_angle)
    return builder.get_commands()[0]


def dxf_ellipse_to_gpgl(
    center_x: float,
    center_y: float,
    major_x: float,
    major_y: float,
    ratio: float,
    start_param: float,
    end_param: float
) -> str:
    """Convert DXF ellipse parameters to GPGL ) command

    DXF ellipses use parametric angles and major axis endpoint.

    Args:
        center_x, center_y: Center in mm
        major_x, major_y: Major axis endpoint relative to center in mm
        ratio: Ratio of minor to major axis (0-1)
        start_param: Start parameter (0 to 2*pi)
        end_param: End parameter (0 to 2*pi)

    Returns:
        GPGL ) command string
    """
    # Calculate major axis length and rotation
    major_length = math.sqrt(major_x**2 + major_y**2)
    minor_length = major_length * ratio
    rotation = math.degrees(math.atan2(major_y, major_x))

    # Convert parametric angles to degrees
    start_angle = math.degrees(start_param)
    end_angle = math.degrees(end_param)

    builder = GPGLCurveBuilder()
    builder.ellipse_mm(
        center_x, center_y,
        major_length, minor_length,
        start_angle, end_angle,
        rotation
    )
    return builder.get_commands()[0]


def spline_to_bezier_segments(
    control_points: List[Tuple[float, float]],
    degree: int = 3
) -> List[Tuple[Tuple[float, float], ...]]:
    """Convert a B-spline to cubic Bezier segments

    This is a simplified conversion for cubic B-splines.
    For more complex splines, use proper B-spline to Bezier conversion.

    Args:
        control_points: Spline control points
        degree: Spline degree (only 3 supported)

    Returns:
        List of Bezier segments, each with 4 control points
    """
    if degree != 3:
        raise ValueError("Only cubic (degree 3) splines are supported")

    if len(control_points) < 4:
        raise ValueError("Need at least 4 control points")

    # For a cubic B-spline, we can approximate with cubic Beziers
    # This is a simplified approach - full conversion is more complex
    segments = []
    n = len(control_points) - 3

    for i in range(n):
        p0 = control_points[i]
        p1 = control_points[i + 1]
        p2 = control_points[i + 2]
        p3 = control_points[i + 3]

        # Approximate conversion (simplified)
        # For accurate conversion, use de Boor algorithm
        segments.append((p0, p1, p2, p3))

    return segments
