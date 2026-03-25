"""
USB communication module for Silhouette cutting machines

Uses pyusb (libusb wrapper) for cross-platform USB communication.
"""

import logging
from typing import Optional, List
from dataclasses import dataclass

try:
    import usb.core
    import usb.util
    USB_AVAILABLE = True
except ImportError:
    USB_AVAILABLE = False

from gpgl.protocol import (
    DEVICES, DeviceInfo,
    USB_ENDPOINT_WRITE, USB_ENDPOINT_READ,
    USB_CHUNK_SIZE, USB_TIMEOUT_MS,
    INIT_SEQUENCE, STATUS_REQUEST, CMD_ETX,
    DeviceStatus
)

logger = logging.getLogger(__name__)


@dataclass
class USBDevice:
    """Represents a connected USB device"""
    device: 'usb.core.Device'
    info: DeviceInfo
    serial: Optional[str] = None


class USBError(Exception):
    """USB communication error"""
    pass


class DeviceNotFoundError(USBError):
    """No compatible device found"""
    pass


class USBCommunication:
    """Handles USB communication with Silhouette cutting machines"""

    def __init__(self):
        if not USB_AVAILABLE:
            raise ImportError("pyusb is not installed. Run: pip install pyusb")
        self._device: Optional[usb.core.Device] = None
        self._device_info: Optional[DeviceInfo] = None
        self._endpoint_out = None
        self._endpoint_in = None

    @property
    def is_connected(self) -> bool:
        """Check if a device is connected"""
        return self._device is not None

    @property
    def device_info(self) -> Optional[DeviceInfo]:
        """Get connected device info"""
        return self._device_info

    def list_devices(self) -> List[USBDevice]:
        """List all connected compatible devices"""
        devices = []

        for name, info in DEVICES.items():
            try:
                found = usb.core.find(
                    idVendor=info.vendor_id,
                    idProduct=info.product_id,
                    find_all=True
                )
                for dev in found:
                    try:
                        serial = usb.util.get_string(dev, dev.iSerialNumber)
                    except Exception:
                        serial = None
                    devices.append(USBDevice(dev, info, serial))
            except usb.core.USBError as e:
                logger.debug(f"Error scanning for {name}: {e}")

        return devices

    def connect(self, device_name: Optional[str] = None) -> DeviceInfo:
        """Connect to a Silhouette cutting machine

        Args:
            device_name: Optional specific device name (e.g., 'cameo5').
                        If None, connects to the first available device.

        Returns:
            DeviceInfo of the connected device

        Raises:
            DeviceNotFoundError: No compatible device found
            USBError: Connection failed
        """
        if self._device is not None:
            self.disconnect()

        # Search for specific device or any compatible device
        if device_name:
            if device_name not in DEVICES:
                raise ValueError(f"Unknown device: {device_name}")
            search_devices = {device_name: DEVICES[device_name]}
        else:
            search_devices = DEVICES

        # Try to find a device
        for name, info in search_devices.items():
            try:
                device = usb.core.find(
                    idVendor=info.vendor_id,
                    idProduct=info.product_id
                )
                if device is not None:
                    self._connect_to_device(device, info)
                    logger.info(f"Connected to {info.name}")
                    return info
            except usb.core.USBError as e:
                logger.debug(f"Failed to connect to {name}: {e}")

        raise DeviceNotFoundError("No compatible Silhouette device found")

    def _connect_to_device(self, device: usb.core.Device, info: DeviceInfo) -> None:
        """Internal method to set up USB connection"""
        self._device = device
        self._device_info = info

        # Detach kernel driver if necessary (Linux)
        try:
            if device.is_kernel_driver_active(0):
                device.detach_kernel_driver(0)
        except (usb.core.USBError, NotImplementedError):
            pass

        # Set configuration
        try:
            device.set_configuration()
        except usb.core.USBError:
            # May already be configured
            pass

        # Get endpoints
        cfg = device.get_active_configuration()
        intf = cfg[(0, 0)]

        self._endpoint_out = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )
        self._endpoint_in = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
        )

        if self._endpoint_out is None or self._endpoint_in is None:
            raise USBError("Could not find USB endpoints")

    def disconnect(self) -> None:
        """Disconnect from the device"""
        if self._device is not None:
            try:
                usb.util.dispose_resources(self._device)
            except Exception as e:
                logger.debug(f"Error during disconnect: {e}")
            finally:
                self._device = None
                self._device_info = None
                self._endpoint_out = None
                self._endpoint_in = None
                logger.info("Disconnected from device")

    def send(self, data: bytes, timeout: int = USB_TIMEOUT_MS) -> int:
        """Send data to the device

        Args:
            data: Bytes to send
            timeout: Timeout in milliseconds

        Returns:
            Number of bytes sent

        Raises:
            USBError: Send failed
        """
        if not self.is_connected:
            raise USBError("Not connected to a device")

        total_sent = 0
        try:
            # Send in chunks
            for i in range(0, len(data), USB_CHUNK_SIZE):
                chunk = data[i:i + USB_CHUNK_SIZE]
                sent = self._endpoint_out.write(chunk, timeout)
                total_sent += sent
        except usb.core.USBError as e:
            raise USBError(f"Failed to send data: {e}")

        return total_sent

    def receive(self, size: int = USB_CHUNK_SIZE, timeout: int = USB_TIMEOUT_MS) -> bytes:
        """Receive data from the device

        Args:
            size: Maximum bytes to receive
            timeout: Timeout in milliseconds

        Returns:
            Received bytes

        Raises:
            USBError: Receive failed
        """
        if not self.is_connected:
            raise USBError("Not connected to a device")

        try:
            data = self._endpoint_in.read(size, timeout)
            return bytes(data)
        except usb.core.USBTimeoutError:
            return b''
        except usb.core.USBError as e:
            raise USBError(f"Failed to receive data: {e}")

    def initialize(self) -> None:
        """Send initialization sequence to the device"""
        if not self.is_connected:
            raise USBError("Not connected to a device")

        self.send(INIT_SEQUENCE + CMD_ETX)
        logger.debug("Sent initialization sequence")

    def get_status(self) -> DeviceStatus:
        """Query device status

        Returns:
            DeviceStatus enum value
        """
        if not self.is_connected:
            raise USBError("Not connected to a device")

        self.send(STATUS_REQUEST)
        response = self.receive(timeout=1000)

        if response:
            # Response is typically a single byte or short string
            try:
                status_value = int(response[0]) if response else 0
                return DeviceStatus(status_value)
            except (ValueError, IndexError):
                return DeviceStatus.READY

        return DeviceStatus.READY

    def get_firmware_version(self) -> str:
        """Query firmware version

        Returns:
            Firmware version string
        """
        if not self.is_connected:
            raise USBError("Not connected to a device")

        self.send(b"FG" + CMD_ETX)
        response = self.receive(timeout=1000)

        if response:
            # Clean up response
            version = response.decode('ascii', errors='ignore').strip()
            # Remove any control characters
            version = ''.join(c for c in version if c.isprintable())
            return version

        return "Unknown"

    def send_command(self, command: bytes) -> None:
        """Send a complete command sequence

        Ensures command is properly terminated with ETX.

        Args:
            command: GPGL command bytes
        """
        if not command.endswith(CMD_ETX):
            command = command + CMD_ETX
        self.send(command)

    def wait_for_ready(self, timeout_seconds: float = 30.0, poll_interval: float = 0.5) -> bool:
        """Wait for device to become ready

        Args:
            timeout_seconds: Maximum time to wait
            poll_interval: Time between status checks in seconds

        Returns:
            True if device is ready, False if timeout
        """
        import time
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            status = self.get_status()
            if status == DeviceStatus.READY:
                return True
            time.sleep(poll_interval)

        return False


def find_cameo5() -> Optional[USBDevice]:
    """Convenience function to find a Cameo 5 device

    Returns:
        USBDevice if found, None otherwise
    """
    if not USB_AVAILABLE:
        return None

    info = DEVICES.get("cameo5")
    if info is None:
        return None

    try:
        device = usb.core.find(
            idVendor=info.vendor_id,
            idProduct=info.product_id
        )
        if device:
            try:
                serial = usb.util.get_string(device, device.iSerialNumber)
            except Exception:
                serial = None
            return USBDevice(device, info, serial)
    except usb.core.USBError:
        pass

    return None
