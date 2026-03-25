#!/usr/bin/env python3
"""
BLE Sniffer for Cameo 5
Captures BLE communication for analysis
"""

import asyncio
import logging
from bleak import BleakClient, BleakScanner

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Cameo 5 UUIDs
WRITE_CHAR = "6d92661d-f429-4d67-929b-28e7a9780912"
STATUS_CHAR = "61490654-b5b4-458c-a867-9e15bc1471e0"
READ_CHAR = "8dcf199a-30e7-4bd4-beb6-beb57dca866c"

received_data = []

def notification_handler(sender, data):
    """Handle incoming notifications"""
    hex_data = data.hex()
    ascii_data = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    logger.info(f"<< RECV [{sender}]: {hex_data} | {ascii_data}")
    received_data.append(data)

async def main():
    logger.info("Scanning for Cameo devices...")

    devices = await BleakScanner.discover(timeout=5.0)
    cameo = None

    for d in devices:
        if d.name and "CAMEO" in d.name.upper():
            cameo = d
            logger.info(f"Found: {d.name} ({d.address})")
            break

    if not cameo:
        logger.error("No Cameo device found!")
        return

    logger.info(f"Connecting to {cameo.name}...")

    async with BleakClient(cameo.address) as client:
        logger.info("Connected! Discovering services...")

        for service in client.services:
            logger.info(f"Service: {service.uuid}")
            for char in service.characteristics:
                logger.info(f"  Char: {char.uuid} - {char.properties}")

        # Enable notifications on all indicate/notify characteristics
        for uuid in [STATUS_CHAR, READ_CHAR]:
            try:
                await client.start_notify(uuid, notification_handler)
                logger.info(f"Enabled notifications on {uuid}")
            except Exception as e:
                logger.warning(f"Could not enable notifications on {uuid}: {e}")

        # Test sending init sequence
        init_sequence = b'\x1b\x04'  # ESC + EOT
        logger.info(f">> SEND init: {init_sequence.hex()}")

        try:
            await client.write_gatt_char(WRITE_CHAR, init_sequence, response=False)
            logger.info("Init sequence sent!")
            await asyncio.sleep(1.0)
        except Exception as e:
            logger.error(f"Init failed: {e}")

        # Test sending status query
        status_query = b'\x1b\x05'  # ESC + ENQ
        logger.info(f">> SEND status query: {status_query.hex()}")

        try:
            await client.write_gatt_char(WRITE_CHAR, status_query, response=False)
            await asyncio.sleep(1.0)
        except Exception as e:
            logger.error(f"Status query failed: {e}")

        # Test simple GPGL command
        test_cmd = b'FG\x03'  # Firmware query
        logger.info(f">> SEND firmware query: {test_cmd.hex()} | FG<ETX>")

        try:
            await client.write_gatt_char(WRITE_CHAR, test_cmd, response=False)
            await asyncio.sleep(2.0)
        except Exception as e:
            logger.error(f"Firmware query failed: {e}")

        # Simple move command
        move_cmd = b'M0,0\x03H\x03'  # Move to origin, home
        logger.info(f">> SEND move: {move_cmd.hex()} | M0,0<ETX>H<ETX>")

        try:
            await client.write_gatt_char(WRITE_CHAR, move_cmd, response=False)
            await asyncio.sleep(2.0)
        except Exception as e:
            logger.error(f"Move failed: {e}")

        logger.info("Test complete. Waiting for any responses...")
        await asyncio.sleep(3.0)

        if received_data:
            logger.info(f"Total received: {len(received_data)} packets")
            for i, data in enumerate(received_data):
                logger.info(f"  Packet {i}: {data.hex()}")
        else:
            logger.info("No data received")

if __name__ == "__main__":
    asyncio.run(main())
