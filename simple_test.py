#!/usr/bin/env python3
"""
Simple BLE Test - Check status and try basic movement
"""

import asyncio
from bleak import BleakClient, BleakScanner

WRITE_CHAR = "6d92661d-f429-4d67-929b-28e7a9780912"
READ_CHAR = "8dcf199a-30e7-4bd4-beb6-beb57dca866c"

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

        await client.start_notify(READ_CHAR, handler)

        # Check status
        print("\n>> Checking status...")
        await client.write_gatt_char(WRITE_CHAR, b'\x1b\x05', response=False)
        await asyncio.sleep(1.0)

        if responses:
            status = responses[-1][0] - ord('0') if responses[-1] else -1
            status_names = {0: "READY", 1: "MOVING", 2: "NO MEDIA (load mat!)"}
            print(f"\n*** Status: {status} = {status_names.get(status, 'UNKNOWN')} ***\n")

            if status == 2:
                print("!!! Please load a cutting mat and press the Load button on your Cameo !!!")
                print("Then run this test again.")
                return
        else:
            print("No status response received")

        # If we got here, try a simple home command
        print(">> Sending home command...")
        await client.write_gatt_char(WRITE_CHAR, b'H\x03', response=False)
        await asyncio.sleep(2.0)

        print("\nDid the cutter head move to home position?")

if __name__ == "__main__":
    asyncio.run(main())
