#!/usr/bin/env python3
"""
BLE Test 3 - Send actual cut commands
"""

import asyncio
import logging
from bleak import BleakClient, BleakScanner

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Cameo 5 UUIDs
WRITE_CHAR = "6d92661d-f429-4d67-929b-28e7a9780912"
READ_CHAR = "8dcf199a-30e7-4bd4-beb6-beb57dca866c"
STATUS_CHAR = "61490654-b5b4-458c-a867-9e15bc1471e0"

def notification_handler(sender, data):
    hex_data = data.hex()
    ascii_data = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    logger.info(f"<< RECV: {hex_data} | {ascii_data}")

async def send_cmd(client, data, desc=""):
    """Send command and wait for response"""
    logger.info(f">> SEND: {data.hex()} | {desc}")
    await client.write_gatt_char(WRITE_CHAR, data, response=False)
    await asyncio.sleep(0.5)

async def main():
    logger.info("Scanning for Cameo devices...")

    devices = await BleakScanner.discover(timeout=5.0)
    cameo = next((d for d in devices if d.name and "CAMEO" in d.name.upper()), None)

    if not cameo:
        logger.error("No Cameo device found!")
        return

    logger.info(f"Connecting to {cameo.name}...")

    async with BleakClient(cameo.address) as client:
        logger.info("Connected!")

        # Enable notifications
        await client.start_notify(READ_CHAR, notification_handler)
        await client.start_notify(STATUS_CHAR, notification_handler)

        # Initialize
        await send_cmd(client, b'\x1b\x04', "ESC+EOT (init)")
        await asyncio.sleep(1.0)

        # Check status
        await send_cmd(client, b'\x1b\x05', "ESC+ENQ (status)")
        await asyncio.sleep(1.0)

        # Get firmware
        await send_cmd(client, b'FG\x03', "FG (firmware)")
        await asyncio.sleep(1.0)

        # Try a complete cut sequence similar to Silhouette Studio
        logger.info("\n=== Sending cut sequence ===")

        # Set orientation (portrait)
        await send_cmd(client, b'FN0\x03', "FN0 (portrait)")

        # Set origin
        await send_cmd(client, b'SO0\x03', "SO0 (origin)")

        # Set cutting mat (12x12)
        await send_cmd(client, b'TG1\x03', "TG1 (12x12 mat)")

        # Select tool 1
        await send_cmd(client, b'J1\x03', "J1 (tool 1)")

        # Set speed
        await send_cmd(client, b'!5,1\x03', "!5,1 (speed 5)")

        # Set force/pressure
        await send_cmd(client, b'FX10,1\x03', "FX10,1 (force 10)")

        # Set cutter offset
        await send_cmd(client, b'FC18,18,1\x03', "FC18,18,1 (offset)")

        # Set lift
        await send_cmd(client, b'FE1,1\x03', "FE1,1 (lift on)")

        # Move to starting position (10mm, 10mm = 200, 200 SU)
        # Note: GPGL uses (y,x) order!
        await send_cmd(client, b'M200,200\x03', "M200,200 (move to 10,10mm)")

        # Draw a small square (10mm x 10mm = 200 SU x 200 SU)
        await send_cmd(client, b'D400,200\x03', "D400,200 (draw right)")
        await send_cmd(client, b'D400,400\x03', "D400,400 (draw down)")
        await send_cmd(client, b'D200,400\x03', "D200,400 (draw left)")
        await send_cmd(client, b'D200,200\x03', "D200,200 (draw up/close)")

        # Home
        await send_cmd(client, b'H\x03', "H (home)")

        # Check status again
        await send_cmd(client, b'\x1b\x05', "ESC+ENQ (final status)")

        logger.info("\n=== Waiting for responses ===")
        await asyncio.sleep(3.0)

if __name__ == "__main__":
    asyncio.run(main())
