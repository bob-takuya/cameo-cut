#!/usr/bin/env python3
"""
BLE Monitor - Watch all BLE traffic to Cameo
Run this BEFORE opening Silhouette Studio
"""

import asyncio
import logging
from datetime import datetime
from bleak import BleakClient, BleakScanner

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

READ_CHAR = "8dcf199a-30e7-4bd4-beb6-beb57dca866c"
STATUS_CHAR = "61490654-b5b4-458c-a867-9e15bc1471e0"

all_data = []

def make_handler(char_name):
    def handler(sender, data):
        hex_data = data.hex()
        ascii_data = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
        logger.info(f"<< {char_name}: {hex_data} | {ascii_data}")
        all_data.append((datetime.now(), char_name, data))
    return handler

async def main():
    logger.info("=== BLE Monitor for Cameo 5 ===")
    logger.info("This will connect to your Cameo and monitor all incoming data.")
    logger.info("Open Silhouette Studio and send a cut to see what commands it uses.")
    logger.info("")

    logger.info("Scanning for Cameo devices...")
    devices = await BleakScanner.discover(timeout=5.0)
    cameo = next((d for d in devices if d.name and "CAMEO" in d.name.upper()), None)

    if not cameo:
        logger.error("No Cameo device found!")
        return

    logger.info(f"Found: {cameo.name} ({cameo.address})")
    logger.info("Connecting...")

    async with BleakClient(cameo.address) as client:
        logger.info("Connected!")
        logger.info("")
        logger.info("=== Monitoring BLE traffic ===")
        logger.info("(Press Ctrl+C to stop)")
        logger.info("")

        # Enable notifications
        await client.start_notify(READ_CHAR, make_handler("READ"))
        await client.start_notify(STATUS_CHAR, make_handler("STATUS"))

        # Keep connection alive
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n=== Monitoring stopped ===")

    if all_data:
        logger.info(f"\nTotal packets received: {len(all_data)}")
        with open("/tmp/ble_capture.txt", "w") as f:
            for ts, char, data in all_data:
                f.write(f"{ts} {char}: {data.hex()}\n")
        logger.info("Saved to /tmp/ble_capture.txt")

if __name__ == "__main__":
    asyncio.run(main())
