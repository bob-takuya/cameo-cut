#!/usr/bin/env python3
"""
Test script to check if Cameo 5 supports position queries
"""

import sys
import asyncio
sys.path.insert(0, '/Users/takuyaitabashi/cameo-cut/src')

from device.bluetooth import BLECommunication

async def test_position_query():
    """Test if we can query current position"""
    print("Testing position query on Cameo 5...")
    print()

    ble = BLECommunication()

    # Scan for devices
    print("Scanning for Cameo devices...")
    devices = await ble.scan_devices(timeout=5.0)

    if not devices:
        print("No Cameo devices found")
        return

    print(f"Found {len(devices)} device(s):")
    for i, dev in enumerate(devices):
        print(f"  [{i}] {dev}")

    # Connect to first device
    device = devices[0]
    print(f"\nConnecting to {device}...")

    success = await ble.connect(device.address)
    if not success:
        print("Failed to connect")
        return

    print("Connected!")

    # Wait a bit for initialization
    await asyncio.sleep(1)

    # Test different position query commands
    print("\n=== Testing Position Query Commands ===\n")

    # Test 1: OA (Output Actual position) - HPGL standard
    print("1. Testing OA (Output Actual) command...")
    try:
        await ble._client.write_gatt_char(
            ble._write_char,
            b'OA\x03',
            response=True
        )
        await asyncio.sleep(0.5)
        response = ble._received_data
        if response:
            print(f"   Response: {response}")
            print(f"   Decoded: {response.decode('ascii', errors='replace')}")
        else:
            print("   No response")
        ble._received_data.clear()
    except Exception as e:
        print(f"   Error: {e}")

    # Test 2: OP (Output P1 and P2)
    print("\n2. Testing OP (Output P1/P2) command...")
    try:
        await ble._client.write_gatt_char(
            ble._write_char,
            b'OP\x03',
            response=True
        )
        await asyncio.sleep(0.5)
        response = ble._received_data
        if response:
            print(f"   Response: {response}")
            print(f"   Decoded: {response.decode('ascii', errors='replace')}")
        else:
            print("   No response")
        ble._received_data.clear()
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: OS (Output Status)
    print("\n3. Testing OS (Output Status) command...")
    try:
        await ble._client.write_gatt_char(
            ble._write_char,
            b'OS\x03',
            response=True
        )
        await asyncio.sleep(0.5)
        response = ble._received_data
        if response:
            print(f"   Response: {response}")
            print(f"   Decoded: {response.decode('ascii', errors='replace')}")
        else:
            print("   No response")
        ble._received_data.clear()
    except Exception as e:
        print(f"   Error: {e}")

    # Test 4: Graphtec-specific position query (if any)
    print("\n4. Testing TB50 (Graphtec query) command...")
    try:
        await ble._client.write_gatt_char(
            ble._write_char,
            b'TB50\x03',
            response=True
        )
        await asyncio.sleep(0.5)
        response = ble._received_data
        if response:
            print(f"   Response: {response}")
            print(f"   Decoded: {response.decode('ascii', errors='replace')}")
        else:
            print("   No response")
        ble._received_data.clear()
    except Exception as e:
        print(f"   Error: {e}")

    print("\n=== Test Complete ===")
    print("\nNote: Position query responses appear on the READ characteristic")
    print("Check if notification handler received any data")

    await ble.disconnect()

if __name__ == "__main__":
    asyncio.run(test_position_query())
