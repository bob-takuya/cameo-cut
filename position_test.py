#!/usr/bin/env python3
"""
Position Test - Draw marks at known positions to verify coordinate system
"""

import asyncio
from bleak import BleakClient, BleakScanner

WRITE_CHAR = "6d92661d-f429-4d67-929b-28e7a9780912"
READ_CHAR = "8dcf199a-30e7-4bd4-beb6-beb57dca866c"
STATUS_CHAR = "61490654-b5b4-458c-a867-9e15bc1471e0"

async def main():
    print("=== Position Test ===")
    print("This will draw marks at specific positions to verify the coordinate system.")
    print("")

    devices = await BleakScanner.discover(timeout=5.0)
    cameo = next((d for d in devices if d.name and "CAMEO" in d.name.upper()), None)

    if not cameo:
        print("No Cameo found!")
        return

    print(f"Connecting to {cameo.name}...")

    def handler(sender, data):
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
        print(f"<< {data.hex()} | {ascii_str}")

    async with BleakClient(cameo.address) as client:
        print("Connected!")

        await client.start_notify(STATUS_CHAR, handler)
        await client.start_notify(READ_CHAR, handler)

        # Initialize all three characteristics
        print("\nInitializing...")
        await client.write_gatt_char(STATUS_CHAR, b'\x1b\x04', response=True)
        await client.write_gatt_char(READ_CHAR, b'\x1b\x04', response=True)
        await client.write_gatt_char(WRITE_CHAR, b'\x1b\x04', response=True)
        await asyncio.sleep(0.5)

        # Check status
        await client.write_gatt_char(WRITE_CHAR, b'\x1b\x05', response=True)
        await asyncio.sleep(0.5)

        print("\n=== Drawing position markers ===")
        print("Using Tool 2 (pen holder)")
        print("")
        print("Markers will be drawn at:")
        print("  1. Origin area (10mm, 10mm) - small cross")
        print("  2. X=100mm, Y=10mm - small cross")
        print("  3. X=10mm, Y=100mm - small cross")
        print("")

        # 1 SU = 0.05mm, so:
        # 10mm = 200 SU
        # 100mm = 2000 SU
        # Cross size: 5mm = 100 SU

        commands = [
            # Setup
            b'FN0\x03',           # Portrait
            b'SO0\x03',           # Origin
            b'J2\x03',            # Tool 2 (pen)
            b'!10,2\x03',         # Speed 10
            b'FX5,2\x03',         # Force 5 (light for pen)

            # Cross 1: at (10mm, 10mm) = (200, 200) SU
            # Note: GPGL uses (Y, X) order!
            b'M200,150\x03',      # Move to start of horizontal line
            b'D200,250\x03',      # Draw horizontal (5mm)
            b'M150,200\x03',      # Move to start of vertical line
            b'D250,200\x03',      # Draw vertical (5mm)

            # Cross 2: at (100mm, 10mm) = (200, 2000) SU
            b'M200,1950\x03',     # Move
            b'D200,2050\x03',     # Horizontal
            b'M150,2000\x03',     # Move
            b'D250,2000\x03',     # Vertical

            # Cross 3: at (10mm, 100mm) = (2000, 200) SU
            b'M2000,150\x03',     # Move
            b'D2000,250\x03',     # Horizontal
            b'M1950,200\x03',     # Move
            b'D2050,200\x03',     # Vertical

            # Home
            b'H\x03',
        ]

        for cmd in commands:
            cmd_str = cmd.decode('ascii', errors='replace').replace('\x03', '')
            print(f">> {cmd_str}")
            await client.write_gatt_char(WRITE_CHAR, cmd, response=True)
            await asyncio.sleep(0.1)

        print("\n=== Waiting for completion ===")
        await asyncio.sleep(3.0)

        print("\n=== Test complete ===")
        print("")
        print("Check your mat for three cross marks:")
        print("  - Cross at (10mm, 10mm) from origin")
        print("  - Cross at (100mm, 10mm) - 90mm to the right")
        print("  - Cross at (10mm, 100mm) - 90mm up/down")
        print("")
        print("The origin (0,0) should be at the bottom-right corner of the mat")
        print("when looking at it from the front of the machine.")

if __name__ == "__main__":
    asyncio.run(main())
