"""
Silhouette Cameo 5 device controller

High-level interface for controlling a Silhouette Cameo 5 cutting machine.
Supports both USB and Bluetooth (BLE) connections.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Union
from enum import Enum, auto

from gpgl.protocol import DeviceStatus, mm_to_su, su_to_mm
from gpgl.commands import GPGLCommandBuilder, ToolSettings

logger = logging.getLogger(__name__)


class ConnectionType(Enum):
    """Connection type"""
    USB = auto()
    BLUETOOTH = auto()


class CuttingAction(Enum):
    """Available cutting actions"""
    CUT = auto()
    SCORE = auto()
    DRAW = auto()
    SKIP = auto()


@dataclass
class ColorSettings:
    """Settings for a specific color"""
    action: CuttingAction = CuttingAction.CUT
    tool: int = 1
    force: int = 10
    speed: int = 5
    depth: int = 3
    passes: int = 1


@dataclass
class CuttingJob:
    """Represents a cutting job"""
    name: str
    commands: bytes
    width_mm: float = 0
    height_mm: float = 0
    entity_count: int = 0


@dataclass
class CameoState:
    """Current state of the Cameo device"""
    connected: bool = False
    device_name: str = ""
    firmware_version: str = ""
    status: DeviceStatus = DeviceStatus.READY
    connection_type: Optional[ConnectionType] = None
    device_address: str = ""  # For Bluetooth


class Cameo5:
    """Controller for Silhouette Cameo 5

    Supports both USB and Bluetooth connections.
    """

    def __init__(self):
        self._usb = None
        self._ble = None
        self._connection_type: Optional[ConnectionType] = None
        self._state = CameoState()
        self._on_status_change: List[Callable[[CameoState], None]] = []

    @property
    def state(self) -> CameoState:
        """Get current device state"""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if device is connected"""
        return self._state.connected

    @property
    def connection_type(self) -> Optional[ConnectionType]:
        """Get current connection type"""
        return self._connection_type

    def add_status_listener(self, callback: Callable[[CameoState], None]) -> None:
        """Add a callback for status changes"""
        self._on_status_change.append(callback)

    def remove_status_listener(self, callback: Callable[[CameoState], None]) -> None:
        """Remove a status change callback"""
        if callback in self._on_status_change:
            self._on_status_change.remove(callback)

    def _notify_status_change(self) -> None:
        """Notify all listeners of status change"""
        for callback in self._on_status_change:
            try:
                callback(self._state)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    def _get_comm(self):
        """Get the current communication interface"""
        if self._connection_type == ConnectionType.USB:
            return self._usb
        elif self._connection_type == ConnectionType.BLUETOOTH:
            return self._ble
        return None

    # === USB Connection ===

    def connect_usb(self, device_name: Optional[str] = None) -> bool:
        """Connect to a Cameo device via USB

        Args:
            device_name: Optional specific device (e.g., 'cameo5', 'cameo5_plus')

        Returns:
            True if connection successful
        """
        try:
            from device.usb import USBCommunication, USBError, DeviceNotFoundError

            if self._usb is None:
                self._usb = USBCommunication()

            # Default to Cameo 5 if not specified
            if device_name is None:
                device_name = "cameo5"

            info = self._usb.connect(device_name)
            self._usb.initialize()

            # Get firmware version
            fw_version = self._usb.get_firmware_version()

            self._connection_type = ConnectionType.USB
            self._state = CameoState(
                connected=True,
                device_name=info.name,
                firmware_version=fw_version,
                status=DeviceStatus.READY,
                connection_type=ConnectionType.USB
            )
            self._notify_status_change()

            logger.info(f"Connected to {info.name} via USB, firmware {fw_version}")
            return True

        except Exception as e:
            logger.warning(f"USB connection failed: {e}")
            return False

    # === Bluetooth Connection ===

    def scan_bluetooth(self, timeout: float = 5.0) -> List[dict]:
        """Scan for Bluetooth devices

        Args:
            timeout: Scan timeout in seconds

        Returns:
            List of discovered devices as dicts with 'address' and 'name'
        """
        try:
            from device.bluetooth import BLECommunication, is_ble_available

            if not is_ble_available():
                logger.warning("Bluetooth not available (install bleak)")
                return []

            if self._ble is None:
                self._ble = BLECommunication()

            devices = self._ble.scan_devices_sync(timeout)
            return [{"address": d.address, "name": d.name, "rssi": d.rssi} for d in devices]

        except Exception as e:
            logger.error(f"Bluetooth scan failed: {e}")
            return []

    def connect_bluetooth(self, address: str) -> bool:
        """Connect to a Cameo device via Bluetooth

        Args:
            address: Bluetooth device address

        Returns:
            True if connection successful
        """
        try:
            from device.bluetooth import BLECommunication, is_ble_available

            if not is_ble_available():
                logger.warning("Bluetooth not available")
                return False

            if self._ble is None:
                self._ble = BLECommunication()

            if not self._ble.connect_sync(address):
                return False

            # BLE initialization is now handled in bluetooth.py connect()
            # which sends ESC+EOT to all three characteristics
            logger.info("BLE connected and initialized")

            self._connection_type = ConnectionType.BLUETOOTH
            self._state = CameoState(
                connected=True,
                device_name="Cameo 5 (Bluetooth)",
                firmware_version="BLE",
                status=DeviceStatus.READY,
                connection_type=ConnectionType.BLUETOOTH,
                device_address=address
            )
            self._notify_status_change()

            logger.info(f"Connected to Cameo via Bluetooth at {address}")
            return True

        except Exception as e:
            logger.error(f"Bluetooth connection failed: {e}")
            return False

    # === Legacy connect method (tries USB first, then Bluetooth) ===

    def connect(self, device_name: Optional[str] = None) -> bool:
        """Connect to a Cameo device (USB first, then Bluetooth)

        Args:
            device_name: Optional specific device name for USB

        Returns:
            True if connection successful
        """
        # Try USB first
        if self.connect_usb(device_name):
            return True

        # Try Bluetooth scan and connect
        logger.info("USB not found, trying Bluetooth...")
        devices = self.scan_bluetooth(timeout=5.0)

        if devices:
            # Connect to first found device
            device = devices[0]
            logger.info(f"Found Bluetooth device: {device['name']}")
            return self.connect_bluetooth(device['address'])

        logger.warning("No Cameo device found via USB or Bluetooth")
        return False

    def disconnect(self) -> None:
        """Disconnect from the device"""
        if self._connection_type == ConnectionType.USB and self._usb:
            self._usb.disconnect()
        elif self._connection_type == ConnectionType.BLUETOOTH and self._ble:
            self._ble.disconnect_sync()

        self._connection_type = None
        self._state = CameoState()
        self._notify_status_change()

    def stop(self) -> bool:
        """Stop the current operation by sending ESC

        Returns:
            True if stop command was sent successfully
        """
        if not self.is_connected:
            return False

        try:
            comm = self._get_comm()
            if comm:
                # Send ESC (0x1B) to stop operation
                stop_cmd = b'\x1b'
                if self._connection_type == ConnectionType.USB:
                    comm.send_command(stop_cmd)
                else:
                    comm.send_single_command_sync(stop_cmd)
                logger.info("Stop command sent")
                return True
        except Exception as e:
            logger.error(f"Stop failed: {e}")

        return False

    def refresh_status(self) -> DeviceStatus:
        """Refresh device status"""
        if not self.is_connected:
            return DeviceStatus.READY

        try:
            comm = self._get_comm()
            if comm:
                status = comm.get_status()
                self._state.status = status
                self._notify_status_change()
                return status
        except Exception:
            pass

        return DeviceStatus.READY

    def send_job(
        self,
        job: CuttingJob,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """Send a cutting job to the device

        Args:
            job: The cutting job to send
            progress_callback: Optional callback(sent_bytes, total_bytes)

        Returns:
            True if job was sent successfully
        """
        if not self.is_connected:
            logger.error("Cannot send job: not connected")
            return False

        try:
            comm = self._get_comm()
            if not comm:
                return False

            import time

            if self._connection_type == ConnectionType.USB:
                # USB: send as chunks
                total_bytes = len(job.commands)
                sent_bytes = 0
                chunk_size = 4096

                for i in range(0, total_bytes, chunk_size):
                    chunk = job.commands[i:i + chunk_size]
                    comm.send(chunk)
                    sent_bytes += len(chunk)
                    if progress_callback:
                        progress_callback(sent_bytes, total_bytes)
            else:
                # Bluetooth: send each command separately
                # Split by ETX and send individually
                commands = job.commands.split(b'\x03')
                total_cmds = len([c for c in commands if c])
                sent_cmds = 0

                # Log first few commands for debugging
                logger.info(f"Sending {total_cmds} commands via Bluetooth:")
                for i, cmd in enumerate(commands[:10]):
                    if cmd:
                        logger.info(f"  [{i}] {cmd.decode('ascii', errors='replace')}")
                if total_cmds > 10:
                    logger.info(f"  ... and {total_cmds - 10} more commands")

                for cmd in commands:
                    if not cmd:
                        continue
                    # Send command with ETX
                    comm.send_single_command_sync(cmd + b'\x03')
                    sent_cmds += 1
                    time.sleep(0.05)  # Small delay between commands

                    if progress_callback:
                        progress_callback(sent_cmds, total_cmds)

            logger.info(f"Sent job '{job.name}': {len(job.commands)} bytes, {total_cmds if self._connection_type == ConnectionType.BLUETOOTH else 'chunked'} commands")
            return True

        except Exception as e:
            logger.error(f"Failed to send job: {e}")
            return False

    def wait_for_completion(
        self,
        timeout_seconds: float = 300,
        poll_interval: float = 1.0
    ) -> bool:
        """Wait for the current job to complete"""
        if self._connection_type == ConnectionType.USB and self._usb:
            return self._usb.wait_for_ready(timeout_seconds, poll_interval)

        # For Bluetooth, just wait
        import time
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            status = self.refresh_status()
            if status == DeviceStatus.READY:
                return True
            time.sleep(poll_interval)
        return False

    def home(self) -> bool:
        """Send the carriage home"""
        if not self.is_connected:
            return False

        try:
            builder = GPGLCommandBuilder()
            builder.home()
            cmd = builder.build()

            comm = self._get_comm()
            if comm:
                comm.send_command(cmd)
                return True
        except Exception:
            pass

        return False

    def move_to(self, x_su: int, y_su: int, toolholder: int = 2) -> bool:
        """Move tool to specified position using ABSOLUTE coordinates from device home

        The coordinates are absolute from the device's home position (top-left corner).
        Origin is at top-left, X increases to the right, Y increases downward.

        Args:
            x_su: X position in SU (1 SU = 0.05mm), absolute from home (0 = left edge)
            y_su: Y position in SU (1 SU = 0.05mm), absolute from home (0 = top edge)
            toolholder: Tool holder to use (1=left/cutter, 2=right/pen)

        Returns:
            True if command was sent successfully
        """
        if not self.is_connected:
            return False

        try:
            comm = self._get_comm()
            if not comm:
                return False

            import time

            x_mm = su_to_mm(x_su)
            y_mm = su_to_mm(y_su)
            logger.info(f"Moving Tool {toolholder} to ({x_mm:.1f}, {y_mm:.1f})mm = ({x_su}, {y_su})SU")

            # *** Bug fix: FN0 / SO0 を move_to から除外 ***
            # FN0 (向き変更) と SO0 (原点再設定) を毎回 move_to() で送ると
            # SO0 が現在位置を原点に再設定してしまい、次の M コマンドが
            # 相対座標として解釈され「加算された座標」に動く原因となる。
            # これらは _create_job() のジョブ初期化時に一度だけ送る。
            # tool positioning では PA + ツール選択 + パラメータ + M のみ送る。
            commands = [
                f"PA",                         # 絶対座標モード（重要）
                f"J{toolholder}",              # ツール選択
                f"!1,{toolholder}",            # 最小力（位置合わせのみ）
                f"FX30,{toolholder}",          # 最高速度
            ]

            # カッターオフセット（ペンは0、ブレードは18）
            offset = 0 if toolholder == 2 else 18
            commands.append(f"FC{offset},{offset},{toolholder}")

            for cmd in commands:
                cmd_bytes = cmd.encode('ascii')
                if self._connection_type == ConnectionType.USB:
                    comm.send_command(cmd_bytes)
                else:
                    comm.send_single_command_sync(cmd_bytes)
                time.sleep(0.05)

            # 移動コマンド（GPGL形式: M<Y>,<X>）
            move_cmd = f"M{y_su},{x_su}".encode('ascii')
            logger.info(f"Sending GPGL: M{y_su},{x_su}")

            if self._connection_type == ConnectionType.USB:
                comm.send_command(move_cmd)
            else:
                comm.send_single_command_sync(move_cmd)

            logger.info(f"Tool {toolholder} move sent")
            return True

        except Exception as e:
            logger.error(f"Move failed: {e}")

        return False

    def test_cut(
        self,
        x_mm: float = 10,
        y_mm: float = 10,
        size_mm: float = 10,
        settings: Optional[ToolSettings] = None
    ) -> bool:
        """Perform a test cut (small square)

        Args:
            x_mm: X position in mm
            y_mm: Y position in mm
            size_mm: Size of test square in mm
            settings: Optional tool settings (uses defaults if None)

        Returns:
            True if test cut was sent successfully
        """
        if not self.is_connected:
            return False

        if settings is None:
            settings = ToolSettings()

        try:
            comm = self._get_comm()
            if not comm:
                return False

            builder = GPGLCommandBuilder()

            # Setup commands (important for cutting)
            builder.set_orientation(False)  # Portrait
            builder.set_origin(0)
            builder.set_cutting_mat(1)  # 12x12 mat

            # Apply tool settings
            builder.apply_tool_settings(settings)

            # Draw a small square
            x = mm_to_su(x_mm)
            y = mm_to_su(y_mm)
            s = mm_to_su(size_mm)

            builder.move_to(x, y)
            builder.draw_to(x + s, y)
            builder.draw_to(x + s, y + s)
            builder.draw_to(x, y + s)
            builder.draw_to(x, y)
            builder.home()

            cmd = builder.build()
            logger.info(f"Sending test cut: {len(cmd)} bytes")
            logger.debug(f"Commands: {cmd}")

            if self._connection_type == ConnectionType.USB:
                comm.send_command(cmd)
            else:
                comm.send_sync(cmd)

            logger.info(f"Sent test cut at ({x_mm}, {y_mm}) mm, size {size_mm} mm")
            return True

        except Exception as e:
            logger.error(f"Test cut failed: {e}")

        return False


def create_job_from_commands(
    name: str,
    builder: GPGLCommandBuilder,
    width_mm: float = 0,
    height_mm: float = 0,
    entity_count: int = 0
) -> CuttingJob:
    """Create a CuttingJob from a command builder"""
    return CuttingJob(
        name=name,
        commands=builder.build(),
        width_mm=width_mm,
        height_mm=height_mm,
        entity_count=entity_count
    )
