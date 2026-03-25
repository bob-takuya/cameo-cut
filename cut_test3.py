#!/usr/bin/env python3
"""
Cut Test 3 - More careful timing and handshake
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

async def send_and_wait(client, char, data, desc, wait=0.5):
    print(f">> {desc}: {data.hex()}")
    await client.write_gatt_char(char, data, response=False)
    await asyncio.sleep(wait)

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

        print("\n=== Full initialization sequence ===")

        # Step 1: Init on all chars with response
        print("\nStep 1: Send ESC+EOT to all chars")
        await client.write_gatt_char(STATUS_CHAR, b'\x1b\x04', response=True)
        await client.write_gatt_char(READ_CHAR, b'\x1b\x04', response=True)
        await client.write_gatt_char(WRITE_CHAR, b'\x1b\x04', response=True)
        await asyncio.sleep(1.0)  # Wait longer

        # Step 2: Status check
        print("\nStep 2: Check status")
        responses.clear()
        await send_and_wait(client, WRITE_CHAR, b'\x1b\x05', "Status query", 1.0)

        if responses and responses[-1][0] == ord('0'):
            print("  -> Status OK (Ready)")
        elif responses and responses[-1][0] == ord('2'):
            print("  -> Status 2 (No media) - Please load mat!")
            return
        else:
            print(f"  -> Unexpected status: {responses}")

        # Step 3: Get firmware version (this worked before)
        print("\nStep 3: Firmware query")
        responses.clear()
        await send_and_wait(client, WRITE_CHAR, b'FG\x03', "Firmware", 1.0)

        if responses:
            print(f"  -> Firmware: {responses[-1]}")

        # Step 4: Setup and cut
        print("\nStep 4: Setup commands")
        setup_cmds = [
            (b'FN0\x03', "Portrait"),
            (b'SO0\x03', "Origin"),
            (b'TG1\x03', "Mat 12x12"),
            (b'J1\x03', "Tool 1"),
            (b'!10,1\x03', "Speed 10"),  # Higher speed
            (b'FX15,1\x03', "Force 15"),  # Higher force
            (b'FC18,18,1\x03', "Offset"),
            (b'FE1,1\x03', "Lift on"),
        ]

        for cmd, desc in setup_cmds:
            await send_and_wait(client, WRITE_CHAR, cmd, desc, 0.2)

        # Step 5: Cut commands
        print("\nStep 5: Cut a small square")
        cut_cmds = [
            (b'M200,200\x03', "Move to 10,10mm"),
            (b'D400,200\x03', "Cut to 20,10mm"),
            (b'D400,400\x03', "Cut to 20,20mm"),
            (b'D200,400\x03', "Cut to 10,20mm"),
            (b'D200,200\x03', "Cut to 10,10mm"),
        ]

        for cmd, desc in cut_cmds:
            await send_and_wait(client, WRITE_CHAR, cmd, desc, 0.3)

        # Step 6: Home
        print("\nStep 6: Home")
        await send_and_wait(client, WRITE_CHAR, b'H\x03', "Home", 2.0)

        # Step 7: Final status
        print("\nStep 7: Final status")
        responses.clear()
        await send_and_wait(client, WRITE_CHAR, b'\x1b\x05', "Status", 1.0)

        if responses:
            status = chr(responses[-1][0])
            print(f"  -> Status: {status}")

        print("\n=== Test complete ===")
        print("Did the cutter move and cut a square?")

if __name__ == "__main__":
    asyncio.run(main())
