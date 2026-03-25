"""
GPGL Protocol definitions for Silhouette Cameo 5

GPGL (Graphtec Plotter Graphics Language) is based on HP-GL but with
Graphtec-specific extensions for cutting machines.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Final


# Protocol constants
CMD_ESC: Final[bytes] = b'\x1b'
CMD_EOT: Final[bytes] = b'\x04'
CMD_ENQ: Final[bytes] = b'\x05'
CMD_ETX: Final[bytes] = b'\x03'

# Initialization sequence
INIT_SEQUENCE: Final[bytes] = CMD_ESC + CMD_EOT
STATUS_REQUEST: Final[bytes] = CMD_ESC + CMD_ENQ
POSITION_REQUEST: Final[bytes] = b'OA'  # Output Actual position (HPGL/GPGL standard)


class DeviceStatus(IntEnum):
    """Device status codes returned by status request"""
    READY = 0
    MOVING = 1
    EMPTY_TRAY = 2


class CuttingMat(IntEnum):
    """Cutting mat types for TG command"""
    NONE = 0
    MAT_12X12 = 1
    MAT_12X24 = 2
    MAT_15X15 = 8
    MAT_24X24 = 9


class Orientation(IntEnum):
    """Page orientation for FN command"""
    PORTRAIT = 0
    LANDSCAPE = 1


@dataclass(frozen=True)
class DeviceInfo:
    """USB device identification"""
    vendor_id: int
    product_id: int
    name: str


# Supported devices
DEVICES: dict[str, DeviceInfo] = {
    "cameo": DeviceInfo(0x0b4d, 0x1121, "Silhouette Cameo"),
    "cameo2": DeviceInfo(0x0b4d, 0x112b, "Silhouette Cameo 2"),
    "cameo3": DeviceInfo(0x0b4d, 0x112f, "Silhouette Cameo 3"),
    "cameo4": DeviceInfo(0x0b4d, 0x1137, "Silhouette Cameo 4"),
    "cameo4_plus": DeviceInfo(0x0b4d, 0x1138, "Silhouette Cameo 4 Plus"),
    "cameo4_pro": DeviceInfo(0x0b4d, 0x1139, "Silhouette Cameo 4 Pro"),
    "cameo5": DeviceInfo(0x0b4d, 0x1140, "Silhouette Cameo 5"),
    "cameo5_plus": DeviceInfo(0x0b4d, 0x1141, "Silhouette Cameo 5 Plus"),
    "portrait3": DeviceInfo(0x0b4d, 0x113a, "Silhouette Portrait 3"),
    "portrait4": DeviceInfo(0x0b4d, 0x113f, "Silhouette Portrait 4"),
}

# USB communication settings
USB_ENDPOINT_WRITE: Final[int] = 0x01
USB_ENDPOINT_READ: Final[int] = 0x82
USB_CHUNK_SIZE: Final[int] = 4096
USB_TIMEOUT_MS: Final[int] = 5000


# Coordinate system
# 1 SU (Silhouette Unit) = 0.05mm
# 1 mm = 20 SU
# 1 inch = 508 SU
SU_PER_MM: Final[float] = 20.0
SU_PER_INCH: Final[float] = 508.0


def mm_to_su(mm: float) -> int:
    """Convert millimeters to Silhouette Units"""
    return round(mm * SU_PER_MM)


def su_to_mm(su: int) -> float:
    """Convert Silhouette Units to millimeters"""
    return su / SU_PER_MM


def inch_to_su(inch: float) -> int:
    """Convert inches to Silhouette Units"""
    return round(inch * SU_PER_INCH)


def su_to_inch(su: int) -> float:
    """Convert Silhouette Units to inches"""
    return su / SU_PER_INCH


# Tool settings limits
@dataclass(frozen=True)
class ToolLimits:
    """Limits for tool settings by device generation"""
    max_speed: int
    max_force: int
    max_depth: int


TOOL_LIMITS_CAMEO3: Final[ToolLimits] = ToolLimits(max_speed=10, max_force=33, max_depth=10)
TOOL_LIMITS_CAMEO4: Final[ToolLimits] = ToolLimits(max_speed=30, max_force=33, max_depth=10)
TOOL_LIMITS_CAMEO5: Final[ToolLimits] = ToolLimits(max_speed=30, max_force=33, max_depth=10)


# DXF color index to common color name mapping
DXF_COLORS: dict[int, str] = {
    0: "black",      # ByBlock
    1: "red",
    2: "yellow",
    3: "green",
    4: "cyan",
    5: "blue",
    6: "magenta",
    7: "white",
    8: "dark_gray",
    9: "light_gray",
    256: "bylayer",  # ByLayer
}
