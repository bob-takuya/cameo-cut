"""
Bluetooth Low Energy (BLE) communication module for Silhouette Cameo

Uses bleak library for cross-platform BLE communication.
"""

import asyncio
import logging
from typing import Optional, List, Callable
from dataclasses import dataclass
from enum import IntEnum

try:
    from bleak import BleakClient, BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.characteristic import BleakGATTCharacteristic
    BLE_AVAILABLE = True
except ImportError:
    BLE_AVAILABLE = False
    # Type stubs for when bleak is not available
    BleakClient = None
    BleakScanner = None
    BLEDevice = None
    BleakGATTCharacteristic = None

from gpgl.protocol import (
    INIT_SEQUENCE, STATUS_REQUEST, POSITION_REQUEST, CMD_ETX,
    DeviceStatus, su_to_mm
)

logger = logging.getLogger(__name__)


# Silhouette Cameo 5 BLE UUIDs (reverse-engineered from Silhouette Studio)
# These are the three characteristics used for communication:
# Index 0: Status - for status queries (has indicate)
CAMEO_STATUS_CHAR_UUID = "61490654-b5b4-458c-a867-9e15bc1471e0"
# Index 1: Read - for reading responses (has indicate)
CAMEO_READ_CHAR_UUID = "8dcf199a-30e7-4bd4-beb6-beb57dca866c"
# Index 2: Write - for sending GPGL commands (write-only, NO indicate)
CAMEO_WRITE_CHAR_UUID = "6d92661d-f429-4d67-929b-28e7a9780912"

# Cameo device name patterns
CAMEO_NAME_PATTERNS = ["Cameo", "CAMEO", "Silhouette", "SILHOUETTE"]


class BLEStatus(IntEnum):
    """BLE connection status codes"""
    DISCONNECTED = 0
    SCANNING = 1
    CONNECTING = 2
    CONNECTED = 3
    ERROR = -1


@dataclass
class BLEDevice:
    """Represents a discovered BLE device"""
    address: str
    name: str
    rssi: int = 0

    def __str__(self):
        return f"{self.name} ({self.address})"


class BLEError(Exception):
    """BLE communication error"""
    pass


class DeviceNotFoundError(BLEError):
    """No compatible device found"""
    pass


class BLECommunication:
    """Handles BLE communication with Silhouette cutting machines"""

    def __init__(self):
        if not BLE_AVAILABLE:
            raise ImportError("bleak is not installed. Run: pip install bleak")

        self._client: Optional[BleakClient] = None
        self._device: Optional[BLEDevice] = None
        self._write_char: Optional[str] = None   # 6D92661D - for GPGL commands
        self._status_char: Optional[str] = None  # 61490654 - for status queries
        self._read_char: Optional[str] = None    # 8DCF199A - for responses
        self._notify_supported: bool = False
        self._status = BLEStatus.DISCONNECTED
        self._received_data: bytearray = bytearray()
        self._data_callback: Optional[Callable[[bytes], None]] = None
        # Create a dedicated event loop for BLE operations
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()

    @property
    def is_connected(self) -> bool:
        """Check if a device is connected"""
        return self._client is not None and self._client.is_connected

    @property
    def status(self) -> BLEStatus:
        """Get current connection status"""
        return self._status

    @property
    def device(self) -> Optional[BLEDevice]:
        """Get connected device info"""
        return self._device

    def _run_async(self, coro):
        """Run async coroutine synchronously using the dedicated loop"""
        return self._loop.run_until_complete(coro)

    async def scan_devices(self, timeout: float = 5.0) -> List[BLEDevice]:
        """Scan for compatible BLE devices

        Args:
            timeout: Scan timeout in seconds

        Returns:
            List of discovered devices
        """
        self._status = BLEStatus.SCANNING
        devices = []

        try:
            logger.info(f"Scanning for BLE devices ({timeout}s)...")
            discovered = await BleakScanner.discover(timeout=timeout)

            for d in discovered:
                name = d.name or "Unknown"
                # Check if device name matches Cameo patterns
                is_cameo = any(pattern in name for pattern in CAMEO_NAME_PATTERNS)

                if is_cameo:
                    device = BLEDevice(
                        address=d.address,
                        name=name,
                        rssi=d.rssi if hasattr(d, 'rssi') else 0
                    )
                    devices.append(device)
                    logger.info(f"Found Cameo device: {device}")

            if not devices:
                # If no Cameo found, list all devices for debugging
                logger.debug("No Cameo devices found. All discovered devices:")
                for d in discovered:
                    logger.debug(f"  {d.name} ({d.address})")

        except Exception as e:
            logger.error(f"Scan error: {e}")
            self._status = BLEStatus.ERROR

        self._status = BLEStatus.DISCONNECTED
        return devices

    def scan_devices_sync(self, timeout: float = 5.0) -> List[BLEDevice]:
        """Synchronous wrapper for scan_devices"""
        return self._run_async(self.scan_devices(timeout))

    async def connect(self, address: str) -> bool:
        """Connect to a device by address

        Args:
            address: BLE device address

        Returns:
            True if connection successful
        """
        if self._client and self._client.is_connected:
            await self.disconnect()

        self._status = BLEStatus.CONNECTING
        logger.info(f"Connecting to {address}...")

        try:
            self._client = BleakClient(address)
            await self._client.connect()

            if not self._client.is_connected:
                raise BLEError("Connection failed")

            # Discover services and characteristics
            await self._discover_characteristics()

            # Set up indication handlers
            if self._status_char:
                try:
                    await self._client.start_notify(
                        self._status_char,
                        self._notification_handler
                    )
                    logger.info("Indications enabled on status characteristic")
                except Exception as e:
                    logger.debug(f"Status char indications not enabled: {e}")

            if self._read_char:
                try:
                    await self._client.start_notify(
                        self._read_char,
                        self._notification_handler
                    )
                    logger.info("Indications enabled on read characteristic")
                    self._notify_supported = True
                except Exception as e:
                    logger.warning(f"Indications not supported on read char: {e}")
                    self._notify_supported = False

            # CRITICAL: Initialize ALL THREE characteristics with ESC+EOT
            # This is required for Cameo 5 BLE to accept commands!
            logger.info("Initializing all characteristics (required for Cameo 5)...")
            init_cmd = b'\x1b\x04'  # ESC + EOT

            if self._status_char:
                await self._client.write_gatt_char(self._status_char, init_cmd, response=True)
                logger.debug("Init sent to status char")

            if self._read_char:
                await self._client.write_gatt_char(self._read_char, init_cmd, response=True)
                logger.debug("Init sent to read char")

            if self._write_char:
                await self._client.write_gatt_char(self._write_char, init_cmd, response=True)
                logger.debug("Init sent to write char")

            await asyncio.sleep(0.5)
            logger.info("BLE initialization complete")

            self._device = BLEDevice(address=address, name="Cameo")
            self._status = BLEStatus.CONNECTED
            logger.info(f"Connected to {address}")
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._status = BLEStatus.ERROR
            self._client = None
            return False

    def connect_sync(self, address: str) -> bool:
        """Synchronous wrapper for connect"""
        return self._run_async(self.connect(address))

    async def _discover_characteristics(self):
        """Discover GATT characteristics for communication

        Based on Silhouette Studio reverse engineering:
        - 61490654: Status characteristic (indicate)
        - 8DCF199A: Read characteristic (indicate)
        - 6D92661D: Write characteristic (write-only, for GPGL data)
        """
        if not self._client:
            return

        self._notify_supported = False
        self._write_char = None   # 6D92661D - for GPGL commands
        self._status_char = None  # 61490654 - for status
        self._read_char = None    # 8DCF199A - for responses

        # Log all services and characteristics for debugging
        logger.info("Discovering BLE services and characteristics...")
        for service in self._client.services:
            logger.info(f"Service: {service.uuid}")
            for char in service.characteristics:
                props = char.properties
                char_uuid_lower = char.uuid.lower()
                logger.info(f"  Char: {char.uuid}, props: {props}")

                # Match specific Cameo UUIDs (case-insensitive)
                if "6d92661d" in char_uuid_lower:
                    # Write characteristic for GPGL data
                    self._write_char = char.uuid
                    logger.info(f"  -> GPGL Write: {char.uuid}")
                elif "61490654" in char_uuid_lower:
                    # Status characteristic
                    self._status_char = char.uuid
                    logger.info(f"  -> Status: {char.uuid}")
                elif "8dcf199a" in char_uuid_lower:
                    # Read characteristic for responses
                    self._read_char = char.uuid
                    if "indicate" in props:
                        self._notify_supported = True
                    logger.info(f"  -> Read: {char.uuid}")

        # Log what we found
        if self._write_char:
            logger.info(f"Using write characteristic: {self._write_char}")
        if self._status_char:
            logger.info(f"Using status characteristic: {self._status_char}")
        if self._read_char:
            logger.info(f"Using read characteristic: {self._read_char}")

        if not self._write_char:
            raise BLEError("No write characteristic (6D92661D) found")

    def _notification_handler(self, sender, data: bytearray):
        """Handle incoming BLE notifications"""
        self._received_data.extend(data)
        logger.debug(f"Received {len(data)} bytes")

        if self._data_callback:
            self._data_callback(bytes(data))

    async def disconnect(self):
        """Disconnect from the device"""
        if self._client:
            try:
                if self._read_char and self._notify_supported:
                    await self._client.stop_notify(self._read_char)
                await self._client.disconnect()
            except Exception as e:
                logger.debug(f"Disconnect error: {e}")
            finally:
                self._client = None
                self._device = None
                self._write_char = None
                self._status_char = None
                self._read_char = None
                self._status = BLEStatus.DISCONNECTED
                logger.info("Disconnected")

    def disconnect_sync(self):
        """Synchronous wrapper for disconnect"""
        self._run_async(self.disconnect())

    async def send(self, data: bytes) -> int:
        """Send data to the device (bulk data transfer)

        Args:
            data: Bytes to send

        Returns:
            Number of bytes sent
        """
        if not self.is_connected or not self._write_char:
            raise BLEError("Not connected")

        try:
            # BLE MTU - use 20 bytes for compatibility
            chunk_size = 20
            total_sent = 0
            total_chunks = (len(data) + chunk_size - 1) // chunk_size

            logger.info(f"Sending {len(data)} bytes in {total_chunks} chunks via {self._write_char}...")

            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]

                # Use response=True for reliable delivery (required for Cameo 5)
                try:
                    await self._client.write_gatt_char(
                        self._write_char,
                        chunk,
                        response=True
                    )
                except Exception:
                    # Fall back to without response if needed
                    await self._client.write_gatt_char(
                        self._write_char,
                        chunk,
                        response=False
                    )

                total_sent += len(chunk)

                # Log progress every 10%
                if total_chunks > 10 and (i // chunk_size) % (total_chunks // 10) == 0:
                    pct = 100 * total_sent // len(data)
                    logger.info(f"Sent {total_sent}/{len(data)} bytes ({pct}%)")

                # Small delay between chunks for flow control
                await asyncio.sleep(0.02)

            logger.info(f"Send complete: {total_sent} bytes")
            return total_sent

        except Exception as e:
            logger.error(f"Send failed at {total_sent} bytes: {e}")
            raise BLEError(f"Send failed: {e}")

    def send_sync(self, data: bytes) -> int:
        """Synchronous wrapper for send"""
        return self._run_async(self.send(data))

    async def receive(self, timeout: float = 1.0) -> bytes:
        """Receive data from the device

        Args:
            timeout: Timeout in seconds

        Returns:
            Received bytes
        """
        if not self.is_connected:
            raise BLEError("Not connected")

        # If notifications are enabled, wait for data
        if self._notify_supported:
            self._received_data.clear()
            await asyncio.sleep(timeout)
            data = bytes(self._received_data)
            self._received_data.clear()
            return data
        else:
            # Use direct read if notifications not supported
            if self._read_char:
                try:
                    data = await self._client.read_gatt_char(self._read_char)
                    return bytes(data)
                except Exception as e:
                    logger.debug(f"Read failed: {e}")
                    return b''
            return b''

    def receive_sync(self, timeout: float = 1.0) -> bytes:
        """Synchronous wrapper for receive"""
        return self._run_async(self.receive(timeout))

    def initialize(self):
        """Send initialization sequence"""
        if not self.is_connected:
            raise BLEError("Not connected")

        self.send_sync(INIT_SEQUENCE + CMD_ETX)
        logger.debug("Sent initialization sequence")

    def get_status(self) -> DeviceStatus:
        """Query device status"""
        if not self.is_connected:
            return DeviceStatus.READY

        try:
            self.send_sync(STATUS_REQUEST)
            response = self.receive_sync(timeout=1.0)

            if response:
                status_value = int(response[0]) if response else 0
                return DeviceStatus(status_value)
        except Exception:
            pass

        return DeviceStatus.READY

    def get_firmware_version(self) -> str:
        """Query firmware version"""
        if not self.is_connected:
            return "Unknown"

        try:
            self.send_sync(b"FG" + CMD_ETX)
            response = self.receive_sync(timeout=1.0)

            if response:
                version = response.decode('ascii', errors='ignore').strip()
                version = ''.join(c for c in version if c.isprintable())
                return version
        except Exception:
            pass

        return "Unknown"

    def get_position(self) -> tuple[float, float] | None:
        """Query current tool position in mm

        Returns:
            (x_mm, y_mm) tuple or None if query fails
        """
        if not self.is_connected:
            return None

        try:
            # Send OA (Output Actual position) command
            self.send_sync(POSITION_REQUEST + CMD_ETX)
            response = self.receive_sync(timeout=1.0)

            if response:
                # Parse response format: "y,x\r\n" in SU
                response_str = response.decode('ascii', errors='ignore').strip()
                logger.debug(f"Position response: {response_str}")

                parts = response_str.split(',')
                if len(parts) == 2:
                    try:
                        y_su = int(parts[0])
                        x_su = int(parts[1])
                        x_mm = su_to_mm(x_su)
                        y_mm = su_to_mm(y_su)
                        return (x_mm, y_mm)
                    except ValueError:
                        logger.warning(f"Failed to parse position: {response_str}")
        except Exception as e:
            logger.warning(f"Failed to query position: {e}")

        return None

    def send_command(self, command: bytes):
        """Send a complete command sequence"""
        if not command.endswith(CMD_ETX):
            command = command + CMD_ETX
        self.send_sync(command)

    async def send_single_command(self, command: bytes):
        """Send a single short command directly without chunking

        This is needed for Cameo 5 which requires each GPGL command
        to be sent as a complete unit.
        """
        if not self.is_connected or not self._write_char:
            raise BLEError("Not connected")

        if not command.endswith(CMD_ETX):
            command = command + CMD_ETX

        # Log the command being sent (for debugging tool selection)
        cmd_str = command.decode('ascii', errors='replace').replace('\x03', '')
        logger.debug(f"BLE send: {cmd_str}")

        await self._client.write_gatt_char(
            self._write_char,
            command,
            response=True
        )

    def send_single_command_sync(self, command: bytes):
        """Synchronous wrapper for send_single_command"""
        return self._run_async(self.send_single_command(command))


def is_ble_available() -> bool:
    """Check if BLE is available"""
    return BLE_AVAILABLE
