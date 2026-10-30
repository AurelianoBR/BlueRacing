# /// script
# requires-python = ">=3.12"
# dependencies = ["bleak>=3.0.2,<4"]
# ///
"""BLE bridge for Bburago Shell Racing Legends cars + serves index.html (Pit Wall UI) on http://localhost:8000.

Connects to every car advertising a name starting with PREFIX, all at once.
Page POSTs {car, fwd, back, left, right, turbo, donut, light, mode} every ~50 ms, where car is a car id,
a list of ids or "all", and gets back {cars: [{id, name, connected, rssi, battery}]}. A car whose page goes quiet
gets idle (watchdog).
"""
import asyncio
import json
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bleak import BleakClient, BleakScanner

PREFIX = "SL-"  # ponytail: name prefix guess for the whole Shell line; switch to service fff0 if another model differs
CMD = "0000fff1-0000-1000-8000-00805f9b34fb"
BATTERY = "00002a19-0000-1000-8000-00805f9b34fb"
PERIOD = 0.05
WATCHDOG = 0.3  # seconds without a POST -> stop the car
IDLE = bytes([1, 0, 0, 0, 0, 0, 0, 0])
KEYS = ("fwd", "back", "left", "right", "turbo", "donut", "light", "mode")

cars = {}  # address -> Car, in discovery order (= car 1, car 2...)
loop = None


class Car:
    def __init__(self, dev):
        self.dev = dev
        self.id = dev.address[-4:]  # macOS gives a UUID; the tail tells cars with the same name apart
        self.state = dict.fromkeys(KEYS, 0)
        self.status = {"connected": False, "rssi": None, "battery": None}
        self.last_post = 0.0
        self.busy = False
        self.wake = asyncio.Event()

    def info(self):
        return {"id": self.id, "name": self.dev.name, **self.status}

    def packet(self):
        # Packet layout:
        # [mode 1|2, up, down, left, right, light, turbo, donut]
        if time.monotonic() - self.last_post > WATCHDOG:
            return IDLE
        s = self.state
        return bytes([2 if s["mode"] else 1, s["fwd"], 0 if s["fwd"] else s["back"], s["left"],
                      0 if s["left"] else s["right"], s["light"], s["turbo"], s["donut"]])


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(Path(__file__).parent), **k)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        new = {k: int(bool(body.get(k))) for k in KEYS}
        target = body.get("car", "all")
        if not isinstance(target, list):
            target = [target]
        for c in list(cars.values()):
            if "all" not in target and c.id not in target:
                continue
            if new != c.state:
                print(f"{c.id}:", "".join(k[0] if v else "." for k, v in new.items()))
                loop.call_soon_threadsafe(c.wake.set)  # send now, don't wait for the next tick
            c.state.update(new)
            c.last_post = time.monotonic()
        out = json.dumps({"cars": [c.info() for c in list(cars.values())]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


async def rssi_poll(car, c):
    # separate task: get_rssi can take a while and must not stall the command writes
    while c.is_connected:
        try:
            # ponytail: private bleak API, macOS-only; public get_rssi was removed from BleakClient
            car.status["rssi"] = await asyncio.wait_for(c._backend.get_rssi(), 1)
        except Exception:
            pass
        await asyncio.sleep(0.5)


async def drive(car):
    try:
        async with BleakClient(car.dev) as c:
            print(f"{car.id}: connected ({car.dev.name})")
            car.status.update(connected=True, battery=(await c.read_gatt_char(BATTERY))[0])
            await c.start_notify(BATTERY, lambda _, d: car.status.update(battery=d[0]))
            rssi_task = asyncio.create_task(rssi_poll(car, c))
            while c.is_connected:
                await c.write_gatt_char(CMD, car.packet(), response=False)
                car.wake.clear()
                try:
                    await asyncio.wait_for(car.wake.wait(), PERIOD)
                except asyncio.TimeoutError:
                    pass
            rssi_task.cancel()
    except Exception as e:
        print(f"{car.id}: BLE error:", e)
    else:
        print(f"{car.id}: disconnected")
    finally:
        car.status.update(connected=False, rssi=None)
        car.busy = False  # next advertisement reconnects


def seen(dev, adv):
    name = adv.local_name or dev.name or ""
    if not name.startswith(PREFIX):
        return
    car = cars.get(dev.address)
    if car is None:
        car = cars[dev.address] = Car(dev)
        print(f"found {name} -> {car.id}")
    if not car.busy:
        car.busy = True
        car.dev = dev
        asyncio.create_task(drive(car))


async def ble():
    global loop
    loop = asyncio.get_running_loop()
    print(f"looking for {PREFIX}*...")
    async with BleakScanner(seen):
        await asyncio.Event().wait()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("open http://localhost:8000")
    asyncio.run(ble())
