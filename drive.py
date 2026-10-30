"""Bburago Shell Racing Legends car over BLE.

Protocol (from github.com/jenkings/BLE-RC-Car-ESP32): write 8 bytes to fff1,
[0x01, forward, backward, left, right, lamp, turbo, 0x00], resent in a loop.
"""
import asyncio
import sys
from bleak import BleakClient, BleakScanner

NAME = "SL-SF-25"
CHAR = "0000fff1-0000-1000-8000-00805f9b34fb"
PERIOD = 0.05  # ponytail: 20 Hz resend, car likely stops if commands stop


def cmd(fwd=0, back=0, left=0, right=0, lamp=0, turbo=0):
    return bytes([1, fwd, back, left, right, lamp, turbo, 0])


async def hold(c, data, secs):
    for _ in range(int(secs / PERIOD)):
        await c.write_gatt_char(CHAR, data, response=False)
        await asyncio.sleep(PERIOD)


async def main():
    dev = await BleakScanner.find_device_by_name(sys.argv[1] if len(sys.argv) > 1 else NAME, timeout=15)
    if not dev:
        raise SystemExit("car not found")
    async with BleakClient(dev) as c:
        await c.start_notify(CHAR, lambda _, d: print("notify", d.hex()))
        for label, data, secs in [
            ("left", cmd(left=1), 1),
            ("right", cmd(right=1), 1),
            ("lamp", cmd(lamp=1), 1),
            ("forward", cmd(fwd=1), 1),
            ("backward", cmd(back=1), 1),
            ("idle", cmd(), 0.5),
        ]:
            print(label)
            await hold(c, data, secs)


asyncio.run(main())
