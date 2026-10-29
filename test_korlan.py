import can

# 1) cari Korlan yang terpasang
print(can.detect_available_configs("usb2can"))
# contoh hasil: [{'interface': 'usb2can', 'channel': '04EF18C4'}]

# 2) buka bus 1 Mbit/s dan tampilkan frame selama 5 detik
bus = can.Bus(interface="usb2can", channel="04EF18C4",
              bitrate=1000000, dll="./usb2can.dll")
import time
t0 = time.time()
while time.time() - t0 < 5:
    msg = bus.recv(timeout=0.5)
    if msg:
        print(msg)
bus.shutdown()
