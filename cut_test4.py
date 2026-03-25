#!/usr/bin/env python3
"""
Cut Test 4 - Use response=True for all writes
"""

import asyncio
from bleak import BleakClient, BleakScanner

WRITE_CHAR = "6d92661d-f429-4d67-929b-28e7a9780912"
READ_CHAR = "8dcf199a-30e7-4bd4-beb6-beb57dca866c"
STATUS_CHAR = "61490654-b5b4-458c-a867-9e15bc1471e0"

responses = []

def handler(sender, data):
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    print(f"<< {data.hex()} | {ascii_str}")
    responses.append(data)

async def main():
    print("Scanning...")
    devices = await BleakScanner.discover(timeout=5.0)
    cameo = next((d for d in devices if d.name and "CAMEO" in d.name.upper()), None)

    if not cameo:
        print("No Cameo found!")
        return

    print(f"Connecting to {cameo.name}...")

    async with BleakClient(cameo.address) as client:
        print("Connected!")

        await client.start_notify(STATUS_CHAR, handler)
        await client.start_notify(READ_CHAR, handler)

        # Exact sequence from simple_test2 that worked:
        print("\n=== Using exact sequence that worked ===")

        print("\nInit on STATUS...")
        await client.write_gatt_char(STATUS_CHAR, b'\x1b\x04', response=True)
        await asyncio.sleep(0.5)

        print("Init on READ...")
        await client.write_gatt_char(READ_CHAR, b'\x1b\x04', response=True)
        await asyncio.sleep(0.5)

        print("Init on WRITE...")
        await client.write_gatt_char(WRITE_CHAR, b'\x1b\x04', response=True)
        await asyncio.sleep(0.5)

        print("\nStatus query (response=True)...")
        responses.clear()
        await client.write_gatt_char(WRITE_CHAR, b'\x1b\x05', response=True)
        await asyncio.sleep(1.0)

        if responses:
            status = chr(responses[-1][0])
            print(f"Status: {status} ({'READY' if status == '0' else 'OTHER'})")
        else:
            print("No status response!")
            # Continue anyway

        print("\nFirmware query...")
        responses.clear()
        await client.write_gatt_char(WRITE_CHAR, b'FG\x03', response=True)
        await asyncio.sleep(1.0)

        # Now send cut commands with response=True
        print("\n=== Sending cut commands with response=True ===")
        commands = [
            b'FN0\x03',
            b'SO0\x03',
            b'J1\x03',
            b'!5,1\x03',
            b'FX10,1\x03',
            b'M200,200\x03',
            b'D400,200\x03',
            b'D400,400\x03',
            b'D200,400\x03',
            b'D200,200\x03',
            b'H\x03',
        ]

        for cmd in commands:
            cmd_str = cmd.decode('ascii', errors='replace').replace('\x03', '<ETX>')
            print(f">> {cmd_str}")
            try:
                await client.write_gatt_char(WRITE_CHAR, cmd, response=True)
            except Exception as e:
                print(f"   Error: {e}")
                # Try without response
                await client.write_gatt_char(WRITE_CHAR, cmd, response=False)
            await asyncio.sleep(0.3)

        print("\n=== Waiting ===")
        await asyncio.sleep(3.0)

        print("\nDid the cutter move?")

if __name__ == "__main__":
    asyncio.run(main())
