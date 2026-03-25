#!/usr/bin/env python3
"""
Test Tool 2 (Pen) movement only - non-interactive
"""
import asyncio
import sys
sys.path.insert(0, 'src')

from bleak import BleakScanner, BleakClient

# Cameo 5 BLE characteristics
WRITE_CHAR = "6d92661d-f429-4d67-929b-28e7a9780912"
STATUS_CHAR = "61490654-b5b4-458c-a867-9e15bc1471e0"
READ_CHAR = "8dcf199a-30e7-4bd4-beb6-beb57dca866c"

async def main():
    print("Scanning for Cameo...")
    devices = await BleakScanner.discover(timeout=5.0)
    cameo = None
    for d in devices:
        if d.name and 'CAMEO' in d.name.upper():
            cameo = d
            break

    if not cameo:
        print("No Cameo found!")
        return

    print(f"Connecting to {cameo.name}...")

    async with BleakClient(cameo.address) as client:
        print("Connected!")

        # Initialize all characteristics
        init_cmd = b'\x1b\x04'  # ESC + EOT
        await client.write_gatt_char(STATUS_CHAR, init_cmd, response=True)
        await client.write_gatt_char(READ_CHAR, init_cmd, response=True)
        await client.write_gatt_char(WRITE_CHAR, init_cmd, response=True)
        print("Initialized")

        await asyncio.sleep(0.5)

        # Full setup exactly like working test_square_pen_v2.gpgl
        print("\n=== Sending Tool 2 (PEN) move commands ===")

        commands = [
            (b'FN0\x03', "FN0 - Portrait orientation"),
            (b'SO0\x03', "SO0 - Origin"),
            (b'J2\x03', "J2 - SELECT TOOL 2 (PEN)"),
            (b'!10,2\x03', "!10,2 - Force 10 for tool 2"),
            (b'FX5,2\x03', "FX5,2 - Speed 5 for tool 2"),
            (b'FC0,0,2\x03', "FC0,0,2 - No offset for pen"),
            (b'FE0,0\x03', "FE0,0 - Lift setting"),
        ]

        for cmd, desc in commands:
            print(f"  {desc}: {cmd}")
            await client.write_gatt_char(WRITE_CHAR, cmd, response=True)
            await asyncio.sleep(0.2)

        print("\n=== NOW MOVING TO (100mm, 100mm) ===")
        print("  Watch which tool moves - should be PEN (right side)")

        await asyncio.sleep(1)

        # Move to 100mm, 100mm = 2000 SU
        move_cmd = b'M2000,2000\x03'
        print(f"  Sending: {move_cmd}")
        await client.write_gatt_char(WRITE_CHAR, move_cmd, response=True)

        await asyncio.sleep(3)

        # Return home
        print("\n=== Returning home ===")
        await client.write_gatt_char(WRITE_CHAR, b'H\x03', response=True)
        await asyncio.sleep(2)

        print("\nDone! Did the PEN (right tool) move?")

if __name__ == "__main__":
    asyncio.run(main())
