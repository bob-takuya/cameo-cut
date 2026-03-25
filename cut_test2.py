#!/usr/bin/env python3
"""
Cut Test 2 - Send all commands as one buffer
"""

import asyncio
from bleak import BleakClient, BleakScanner

WRITE_CHAR = "6d92661d-f429-4d67-929b-28e7a9780912"
READ_CHAR = "8dcf199a-30e7-4bd4-beb6-beb57dca866c"
STATUS_CHAR = "61490654-b5b4-458c-a867-9e15bc1471e0"

async def main():
    print("Scanning...")
    devices = await BleakScanner.discover(timeout=5.0)
    cameo = next((d for d in devices if d.name and "CAMEO" in d.name.upper()), None)

    if not cameo:
        print("No Cameo found!")
        return

    print(f"Connecting to {cameo.name}...")

    def handler(sender, data):
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
        print(f"<< Response: {data.hex()} | {ascii_str}")

    async with BleakClient(cameo.address) as client:
        print("Connected!")

        await client.start_notify(STATUS_CHAR, handler)
        await client.start_notify(READ_CHAR, handler)

        # Initialize all three characteristics
        print("\n=== Initializing ===")
        await client.write_gatt_char(STATUS_CHAR, b'\x1b\x04', response=True)
        await client.write_gatt_char(READ_CHAR, b'\x1b\x04', response=True)
        await client.write_gatt_char(WRITE_CHAR, b'\x1b\x04', response=True)
        await asyncio.sleep(0.5)

        # Check status
        print("\n=== Checking status ===")
        await client.write_gatt_char(WRITE_CHAR, b'\x1b\x05', response=False)
        await asyncio.sleep(0.5)

        # Build complete command buffer
        print("\n=== Building command buffer ===")
        cmd = b''
        cmd += b'FN0\x03'       # Portrait
        cmd += b'SO0\x03'       # Origin
        cmd += b'TG1\x03'       # 12x12 mat
        cmd += b'J1\x03'        # Tool 1
        cmd += b'!5,1\x03'      # Speed 5
        cmd += b'FX10,1\x03'    # Force 10
        cmd += b'FC18,18,1\x03' # Offset
        cmd += b'FE1,1\x03'     # Lift on
        cmd += b'M200,200\x03'  # Move to start
        cmd += b'D400,200\x03'  # Draw right
        cmd += b'D400,400\x03'  # Draw down
        cmd += b'D200,400\x03'  # Draw left
        cmd += b'D200,200\x03'  # Draw up/close
        cmd += b'H\x03'         # Home

        print(f"Total command size: {len(cmd)} bytes")
        print(f"Commands: {cmd}")

        # Send as single write
        print("\n=== Sending as single buffer ===")
        await client.write_gatt_char(WRITE_CHAR, cmd, response=False)

        print("\n=== Waiting for completion ===")
        await asyncio.sleep(5.0)

        # Check final status
        print("\n=== Final status ===")
        await client.write_gatt_char(WRITE_CHAR, b'\x1b\x05', response=False)
        await asyncio.sleep(1.0)

        print("\nDid the cutter move?")

if __name__ == "__main__":
    asyncio.run(main())
