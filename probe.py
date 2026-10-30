"""Subscribe to every notify characteristic and print what arrives while sending idle."""
import asyncio
from bleak import BleakClient, BleakScanner

NAME = "SL-SF-25"
CMD = "0000fff1-0000-1000-8000-00805f9b34fb"
IDLE = bytes([1, 0, 0, 0, 0, 0, 0, 0])


async def main():
    dev = await BleakScanner.find_device_by_name(NAME, timeout=15)
    if not dev:
        raise SystemExit("car not found (page in Chrome still connected?)")
    async with BleakClient(dev) as c:
        for s in c.services:
            for ch in s.characteristics:
                if "notify" in ch.properties:
                    await c.start_notify(ch, lambda h, d, u=ch.uuid[4:8]: print(u, d.hex()))
                    print("subscribed", ch.uuid[4:8])
        for _ in range(100):  # 5 s
            await c.write_gatt_char(CMD, IDLE, response=False)
            await asyncio.sleep(0.05)


asyncio.run(main())
