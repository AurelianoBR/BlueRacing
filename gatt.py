import asyncio
from bleak import BleakClient, BleakScanner

NAME = "SL-SF-25"


async def main():
    dev = await BleakScanner.find_device_by_name(NAME, timeout=15)
    if not dev:
        raise SystemExit(f"{NAME} not found")
    async with BleakClient(dev) as c:
        for s in c.services:
            print("service", s.uuid, s.description)
            for ch in s.characteristics:
                line = f"  char {ch.uuid} {ch.properties}"
                if "read" in ch.properties:
                    try:
                        line += f" = {(await c.read_gatt_char(ch)).hex()}"
                    except Exception as e:
                        line += f" (read err {e})"
                print(line)


asyncio.run(main())
