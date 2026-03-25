"""
GPGL Command generation for Silhouette Cameo

This module provides functions to generate GPGL commands for controlling
Silhouette cutting machines.
"""

from dataclasses import dataclass
from typing import List, Tuple

from .protocol import CMD_ETX, mm_to_su


@dataclass
class ToolSettings:
    """Settings for a cutting/drawing tool"""
    toolholder: int = 1  # 1 or 2
    force: int = 10      # 1-33 (40 for Cameo 5 Alpha)
    speed: int = 5       # 1-30
    depth: int = 3       # 0-10 (AutoBlade only)
    offset_x: int = 18   # Cutter offset in SU (0.9mm for standard blade)
    offset_y: int = 18
    lift_between_paths: bool = True

    def validate(self) -> None:
        """Validate tool settings are within allowed ranges"""
        if self.toolholder not in (1, 2):
            raise ValueError(f"toolholder must be 1 or 2, got {self.toolholder}")
        if not 1 <= self.force <= 40:
            raise ValueError(f"force must be 1-40, got {self.force}")
        if not 1 <= self.speed <= 30:
            raise ValueError(f"speed must be 1-30, got {self.speed}")
        if not 0 <= self.depth <= 10:
            raise ValueError(f"depth must be 0-10, got {self.depth}")


class GPGLCommandBuilder:
    """Builder for GPGL command sequences"""

    def __init__(self):
        self._commands: List[str] = []

    def add(self, command: str) -> 'GPGLCommandBuilder':
        """Add a command to the sequence"""
        self._commands.append(command)
        return self

    def build(self) -> bytes:
        """Build the final command sequence as bytes

        Each command is terminated with ETX (0x03) for Cameo 5 compatibility.
        """
        # Each command needs its own ETX terminator
        result = b''
        for cmd in self._commands:
            result += cmd.encode('ascii') + CMD_ETX
        return result

    def clear(self) -> 'GPGLCommandBuilder':
        """Clear all commands"""
        self._commands.clear()
        return self

    # === Initialization Commands ===

    def firmware_version(self) -> 'GPGLCommandBuilder':
        """Query firmware version (FG command)"""
        return self.add("FG")

    def set_orientation(self, landscape: bool = False) -> 'GPGLCommandBuilder':
        """Set page orientation (FN command)"""
        return self.add(f"FN{1 if landscape else 0}")

    def set_cutting_mat(self, mat_type: int) -> 'GPGLCommandBuilder':
        """Set cutting mat type (TG command)
        0=none, 1=12x12, 2=12x24, 8=15x15, 9=24x24
        """
        return self.add(f"TG{mat_type}")

    def set_media_type(self, media_type: int) -> 'GPGLCommandBuilder':
        """Set media type (FW command)"""
        return self.add(f"FW{media_type}")

    def set_track_enhance(self, enabled: bool = True) -> 'GPGLCommandBuilder':
        """Enable/disable track enhancement (FY command)
        Moves media back and forth for better grip
        """
        return self.add(f"FY{0 if enabled else 1}")

    # === Boundary Commands ===

    def set_upper_left(self, x: int, y: int) -> 'GPGLCommandBuilder':
        """Set upper-left boundary in SU (\\ command)"""
        return self.add(f"\\{y},{x}")

    def set_lower_right(self, x: int, y: int) -> 'GPGLCommandBuilder':
        """Set lower-right boundary in SU (Z command)"""
        return self.add(f"Z{y},{x}")

    def set_origin(self, origin: int = 0) -> 'GPGLCommandBuilder':
        """Set origin point (SO command)"""
        return self.add(f"SO{origin}")

    # === Tool Selection Commands ===

    def select_tool(self, toolholder: int) -> 'GPGLCommandBuilder':
        """Select tool holder (J command)"""
        if toolholder not in (1, 2):
            raise ValueError(f"toolholder must be 1 or 2, got {toolholder}")
        return self.add(f"J{toolholder}")

    def set_force(self, force: int, toolholder: int = 1) -> 'GPGLCommandBuilder':
        """Set cutting force/pressure (! command)"""
        return self.add(f"!{force},{toolholder}")

    def set_speed(self, speed: int, toolholder: int = 1) -> 'GPGLCommandBuilder':
        """Set cutting speed (FX command)"""
        return self.add(f"FX{speed},{toolholder}")

    def set_depth(self, depth: int, toolholder: int = 1) -> 'GPGLCommandBuilder':
        """Set blade depth for AutoBlade (TF command)"""
        return self.add(f"TF{depth},{toolholder}")

    def set_cutter_offset(self, x: int, y: int, toolholder: int = 1) -> 'GPGLCommandBuilder':
        """Set cutter offset in SU (FC command)"""
        return self.add(f"FC{x},{y},{toolholder}")

    def set_lift_between_paths(self, lift: bool, toolholder: int = 1) -> 'GPGLCommandBuilder':
        """Enable/disable lifting between paths (FE command)"""
        return self.add(f"FE{1 if lift else 0},{toolholder}")

    def set_corner_sharpen(self, start: int, end: int, toolholder: int = 1) -> 'GPGLCommandBuilder':
        """Set corner sharpening/overcut (FF command)"""
        return self.add(f"FF{start},{end},{toolholder}")

    def apply_tool_settings(self, settings: ToolSettings) -> 'GPGLCommandBuilder':
        """Apply all tool settings at once"""
        settings.validate()

        # For pen (tool 2), use 0 offset. For cutter (tool 1), use specified offset.
        offset_x = 0 if settings.toolholder == 2 else settings.offset_x
        offset_y = 0 if settings.toolholder == 2 else settings.offset_y

        return (self
            .select_tool(settings.toolholder)
            .set_force(settings.force, settings.toolholder)
            .set_speed(settings.speed, settings.toolholder)
            .set_depth(settings.depth, settings.toolholder)
            .set_cutter_offset(offset_x, offset_y, settings.toolholder)
            .set_lift_between_paths(settings.lift_between_paths, settings.toolholder))

    # === Movement Commands ===

    def move_to(self, x: int, y: int) -> 'GPGLCommandBuilder':
        """Move without cutting (M command)
        Note: GPGL uses (y, x) order!
        """
        return self.add(f"M{y},{x}")

    def draw_to(self, x: int, y: int) -> 'GPGLCommandBuilder':
        """Draw/cut to position (D command)
        Note: GPGL uses (y, x) order!
        """
        return self.add(f"D{y},{x}")

    def home(self) -> 'GPGLCommandBuilder':
        """Return to home position (H command)"""
        return self.add("H")

    # === Path Commands ===

    def line(self, x1: int, y1: int, x2: int, y2: int) -> 'GPGLCommandBuilder':
        """Draw a line from (x1,y1) to (x2,y2)"""
        return self.move_to(x1, y1).draw_to(x2, y2)

    def polyline(self, points: List[Tuple[int, int]], closed: bool = False) -> 'GPGLCommandBuilder':
        """Draw a polyline through given points"""
        if len(points) < 2:
            return self

        # Move to first point
        self.move_to(points[0][0], points[0][1])

        # Draw to remaining points
        for x, y in points[1:]:
            self.draw_to(x, y)

        # Close path if requested
        if closed and len(points) > 2:
            self.draw_to(points[0][0], points[0][1])

        return self

    # === Convenience Methods ===

    def move_to_mm(self, x_mm: float, y_mm: float) -> 'GPGLCommandBuilder':
        """Move to position in millimeters"""
        return self.move_to(mm_to_su(x_mm), mm_to_su(y_mm))

    def draw_to_mm(self, x_mm: float, y_mm: float) -> 'GPGLCommandBuilder':
        """Draw to position in millimeters"""
        return self.draw_to(mm_to_su(x_mm), mm_to_su(y_mm))

    def line_mm(self, x1: float, y1: float, x2: float, y2: float) -> 'GPGLCommandBuilder':
        """Draw a line using millimeter coordinates"""
        return self.line(
            mm_to_su(x1), mm_to_su(y1),
            mm_to_su(x2), mm_to_su(y2)
        )


def create_init_sequence() -> bytes:
    """Create standard initialization command sequence"""
    builder = GPGLCommandBuilder()
    return (builder
        .set_orientation(False)     # Portrait
        .set_origin(0)
        .build())


def create_job(
    tool_settings: ToolSettings,
    commands_func,  # Callable that takes GPGLCommandBuilder
    boundary: Tuple[int, int, int, int] | None = None  # (x1, y1, x2, y2) in SU
) -> bytes:
    """Create a complete cutting job

    Args:
        tool_settings: Tool configuration
        commands_func: Function that adds drawing commands to builder
        boundary: Optional boundary rectangle in SU

    Returns:
        Complete GPGL command sequence as bytes
    """
    builder = GPGLCommandBuilder()

    # Set boundary if provided
    if boundary:
        x1, y1, x2, y2 = boundary
        builder.set_upper_left(x1, y1).set_lower_right(x2, y2)

    # Apply tool settings
    builder.apply_tool_settings(tool_settings)

    # Add user commands
    commands_func(builder)

    # Return home
    builder.home()

    return builder.build()
