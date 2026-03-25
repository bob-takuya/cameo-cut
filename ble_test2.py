#!/usr/bin/env python3
"""
BLE Test 2 - Try different characteristics
"""

import asyncio
import logging
from bleak import BleakClient, BleakScanner

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Cameo 5 UUIDs
CHARS = {
    "STATUS": "61490654-b5b4-458c-a867-9e15bc1471e0",  # write, indicate
    "READ": "8dcf199a-30e7-4bd4-beb6-beb57dca866c",    # write, indicate
    "WRITE": "6d92661d-f429-4d67-929b-28e7a9780912",   # write only
}

def notification_handler(sender, data):
    """Handle incoming notifications"""
    hex_data = data.hex()
    ascii_data = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    logger.info(f"<< RECV from {sender}: {hex_data} | {ascii_data}")

async def main():
    logger.info("Scanning for Cameo devices...")

    devices = await BleakScanner.discover(timeout=5.0)
    cameo = None

    for d in devices:
        if d.name and "CAMEO" in d.name.upper():
            cameo = d
            break

    if not cameo:
        logger.error("No Cameo device found!")
        return

    logger.info(f"Connecting to {cameo.name}...")

    async with BleakClient(cameo.address) as client:
        logger.info("Connected!")

        # Enable notifications on both indicate characteristics
        for name, uuid in [("STATUS", CHARS["STATUS"]), ("READ", CHARS["READ"])]:
            try:
                await client.start_notify(uuid, notification_handler)
                logger.info(f"Enabled indications on {name}")
            except Exception as e:
                logger.warning(f"Could not enable indications on {name}: {e}")

        # Try sending to EACH characteristic and see what happens
        test_data = [
            (b'\x1b\x04', "ESC+EOT (init)"),
            (b'\x1b\x05', "ESC+ENQ (status)"),
            (b'FG\x03', "FG (firmware)"),
        ]

        for char_name, char_uuid in CHARS.items():
            logger.info(f"\n=== Testing characteristic: {char_name} ({char_uuid}) ===")

            for data, desc in test_data:
                logger.info(f">> Sending to {char_name}: {data.hex()} ({desc})")
                try:
                    # Try with response first
                    try:
                        await client.write_gatt_char(char_uuid, data, response=True)
                        logger.info(f"   Sent with response OK")
                    except Exception as e1:
                        # Fall back to without response
                        await client.write_gatt_char(char_uuid, data, response=False)
                        logger.info(f"   Sent without response OK")

                    await asyncio.sleep(1.0)
                except Exception as e:
                    logger.error(f"   Failed: {e}")

        # Wait for any delayed responses
        logger.info("\nWaiting for responses...")
        await asyncio.sleep(3.0)

        # Try reading from characteristics
        logger.info("\n=== Trying to read characteristics ===")
        for name, uuid in CHARS.items():
            try:
                data = await client.read_gatt_char(uuid)
                logger.info(f"Read from {name}: {data.hex()} | {''.join(chr(b) if 32<=b<127 else '.' for b in data)}")
            except Exception as e:
                logger.info(f"Cannot read from {name}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
