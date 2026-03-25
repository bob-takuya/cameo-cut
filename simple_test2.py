#!/usr/bin/env python3
"""
Simple BLE Test 2 - Try the exact sequence that worked before
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

    responses = []

    def handler(sender, data):
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
        print(f"<< Response: {data.hex()} | {ascii_str}")
        responses.append(data)

    async with BleakClient(cameo.address) as client:
        print("Connected!")

        # Enable notifications on BOTH characteristics
        await client.start_notify(STATUS_CHAR, handler)
        await client.start_notify(READ_CHAR, handler)
        print("Notifications enabled")

        # This is the exact sequence that got responses in test2:
        # First send to STATUS and READ, then to WRITE

        print("\n>> Step 1: Send init to STATUS char...")
        await client.write_gatt_char(STATUS_CHAR, b'\x1b\x04', response=True)
        await asyncio.sleep(0.5)

        print(">> Step 2: Send init to READ char...")
        await client.write_gatt_char(READ_CHAR, b'\x1b\x04', response=True)
        await asyncio.sleep(0.5)

        print(">> Step 3: Send init to WRITE char...")
        await client.write_gatt_char(WRITE_CHAR, b'\x1b\x04', response=True)
        await asyncio.sleep(0.5)

        print("\n>> Step 4: Send status query to WRITE char...")
        await client.write_gatt_char(WRITE_CHAR, b'\x1b\x05', response=True)
        await asyncio.sleep(1.0)

        if responses:
            print(f"\n=== Got {len(responses)} response(s)! ===")
            for i, r in enumerate(responses):
                status = r[0] - ord('0') if r[0] >= ord('0') and r[0] <= ord('9') else -1
                status_names = {0: "READY", 1: "MOVING", 2: "NO MEDIA"}
                if status >= 0:
                    print(f"  Status: {status} = {status_names.get(status, 'UNKNOWN')}")
        else:
            print("\n=== No responses received ===")

        # Try firmware query
        print("\n>> Firmware query...")
        await client.write_gatt_char(WRITE_CHAR, b'FG\x03', response=False)
        await asyncio.sleep(1.0)

        if len(responses) > 0:
            print(f"Latest response: {responses[-1]}")

        # Try home command
        print("\n>> Home command...")
        await client.write_gatt_char(WRITE_CHAR, b'H\x03', response=False)
        await asyncio.sleep(2.0)

        print("\nDid the cutter head move?")

if __name__ == "__main__":
    asyncio.run(main())
