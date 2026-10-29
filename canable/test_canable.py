import time

import can
from serial.tools import list_ports

# 1) tampilkan port COM; CANable (firmware slcan) punya VID 16D0
for p in list_ports.comports():
    print(p.device, p.description, hex(p.vid or 0))
# contoh hasil: COM7 USB Serial Device (COM7) 0x16d0

# 2) buka bus 1 Mbit/s dan tampilkan frame selama 5 detik (ganti COM7 dengan port Anda)
bus = can.Bus(interface="slcan", channel="COM7", bitrate=1000000)
t0 = time.time()
while time.time() - t0 < 5:
    msg = bus.recv(timeout=0.5)
    if msg:
        print(msg)
bus.shutdown()
