#!/usr/bin/env python3
"""
Send GPGL File - Send a .gpgl file to the Cameo
Usage: python send_gpgl.py <file.gpgl>
"""

import sys
import asyncio
from pathlib import Path
from bleak import BleakClient, BleakScanner

WRITE_CHAR = "6d92661d-f429-4d67-929b-28e7a9780912"
READ_CHAR = "8dcf199a-30e7-4bd4-beb6-beb57dca866c"
STATUS_CHAR = "61490654-b5b4-458c-a867-9e15bc1471e0"


def parse_gpgl_file(filepath: str) -> list:
    """Parse a .gpgl file and return list of commands"""
    commands = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith(';'):
                continue
            # Add ETX terminator if not present
            cmd = line.encode('ascii')
            if not cmd.endswith(b'\x03'):
                cmd += b'\x03'
            commands.append(cmd)
    return commands


async def main(filepath: str):
    print(f"=== Send GPGL File ===")
    print(f"File: {filepath}")
    print("")

    # Parse file
    commands = parse_gpgl_file(filepath)
    print(f"Loaded {len(commands)} commands")

    # Find Cameo
    print("\nScanning for Cameo...")
    devices = await BleakScanner.discover(timeout=5.0)
    cameo = next((d for d in devices if d.name and "CAMEO" in d.name.upper()), None)

    if not cameo:
        print("No Cameo found!")
        return

    print(f"Connecting to {cameo.name}...")

    def handler(sender, data):
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
        print(f"<< {ascii_str}")

    async with BleakClient(cameo.address) as client:
        print("Connected!")

        await client.start_notify(STATUS_CHAR, handler)
        await client.start_notify(READ_CHAR, handler)

        # Initialize
        print("\nInitializing...")
        await client.write_gatt_char(STATUS_CHAR, b'\x1b\x04', response=True)
        await client.write_gatt_char(READ_CHAR, b'\x1b\x04', response=True)
        await client.write_gatt_char(WRITE_CHAR, b'\x1b\x04', response=True)
        await asyncio.sleep(0.5)

        # Send commands
        print(f"\nSending {len(commands)} commands...")
        for i, cmd in enumerate(commands):
            cmd_str = cmd.decode('ascii', errors='replace').replace('\x03', '')
            print(f"  [{i+1}/{len(commands)}] {cmd_str}")
            await client.write_gatt_char(WRITE_CHAR, cmd, response=True)
            await asyncio.sleep(0.1)

        print("\nWaiting for completion...")
        await asyncio.sleep(3.0)

        print("\nDone!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python send_gpgl.py <file.gpgl>")
        print("")
        print("Examples:")
        print("  python send_gpgl.py examples/test_square_pen.gpgl")
        print("  python send_gpgl.py examples/position_test.gpgl")
        sys.exit(1)

    filepath = sys.argv[1]
    if not Path(filepath).exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    asyncio.run(main(filepath))
