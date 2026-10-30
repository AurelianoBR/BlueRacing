import asyncio
from bleak import BleakScanner


async def main():
    found = await BleakScanner.discover(timeout=15, return_adv=True)
    for addr, (dev, adv) in sorted(found.items(), key=lambda x: -x[1][1].rssi):
        print(f"{adv.rssi:>4} dBm  {addr}  {adv.local_name or dev.name or '-'}")
        if adv.service_uuids:
            print("       services:", adv.service_uuids)
        if adv.manufacturer_data:
            print("       mfr:", {k: v.hex() for k, v in adv.manufacturer_data.items()})


asyncio.run(main())
