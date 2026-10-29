#!/usr/bin/env python3
"""
csp_can_tool.py - membaca dan menguji bus CAN CubeSat (libcsp 1.6 / CFP)
memakai Makerbase CANable V2.0 Pro (firmware slcan) dan python-can.

Bisa dipakai untuk:
  monitor  : menampilkan semua frame CAN + paket CSP yang sudah disusun ulang
  ping     : ping node CSP (OBC = 1, EPS = 2)
  hk       : minta data housekeeping EPS (port 12)
  payload  : perintah ON/OFF rail payload EPS (port 13)
  echo     : kirim pesan teks ke port 10 dan tampilkan balasannya

Contoh (Windows):
  python csp_can_tool.py list
  python csp_can_tool.py --channel COM7 monitor
  python csp_can_tool.py --channel COM7 ping 2
  python csp_can_tool.py --channel COM7 hk
  python csp_can_tool.py --channel COM7 payload on
  python csp_can_tool.py --channel COM7 echo 1 "Halo OBC"

Tanpa --channel, port COM CANable dicari otomatis.

Kebutuhan:
  pip install python-can pyserial
  CANable dengan firmware slcan (muncul sebagai port COM, tanpa driver/DLL).
"""
import argparse
import queue
import struct
import threading
import time

import can

try:
    from serial.tools import list_ports
except ImportError:  # pyserial belum terpasang
    list_ports = None

# ---------------------------------------------------------------------------
# Konstanta sistem (harus sama dengan firmware: cubesat_proto.h)
# ---------------------------------------------------------------------------
ADDR_OBC = 1
ADDR_EPS = 2
ADDR_PC = 10        # alamat CSP untuk PC/CANable (bebas, asal unik 0..30)

PORT_PING = 1
PORT_ECHO = 10
PORT_TLM = 11
PORT_EPS_HK = 12
PORT_EPS_CMD = 13

NODE_NAMES = {ADDR_OBC: "OBC", ADDR_EPS: "EPS", ADDR_PC: "PC", 31: "BCAST"}
PORT_NAMES = {0: "CMP", 1: "PING", 2: "PS", 3: "MEMFREE", 4: "REBOOT",
              5: "BUF_FREE", 6: "UPTIME", PORT_ECHO: "ECHO",
              PORT_TLM: "TLM", PORT_EPS_HK: "EPS_HK", PORT_EPS_CMD: "EPS_CMD"}

# eps_hk_t (20 byte, little endian, packed)
EPS_HK_FMT = "<IhHBBHII"
EPS_HK_SIZE = struct.calcsize(EPS_HK_FMT)

# VID:PID CANable firmware slcan (USB CDC)
CANABLE_SLCAN_VID = 0x16D0
CANABLE_SLCAN_PID = 0x117E

# ---------------------------------------------------------------------------
# CFP: CAN Fragmentation Protocol (ID extended 29 bit)
# [SRC 5][DST 5][TYPE 1][REMAIN 8][ID 10]
# ---------------------------------------------------------------------------
CFP_BEGIN, CFP_MORE = 0, 1
CFP_OVERHEAD = 6    # 4 byte header CSP + 2 byte panjang


def cfp_fields(can_id):
    return {
        "src": (can_id >> 24) & 0x1F,
        "dst": (can_id >> 19) & 0x1F,
        "type": (can_id >> 18) & 0x01,
        "remain": (can_id >> 10) & 0xFF,
        "id": can_id & 0x3FF,
    }


def cfp_make_id(src, dst, typ, remain, ident):
    return ((src & 0x1F) << 24) | ((dst & 0x1F) << 19) | ((typ & 1) << 18) \
        | ((remain & 0xFF) << 10) | (ident & 0x3FF)


# ---------------------------------------------------------------------------
# Header CSP 1.6 (32 bit, dikirim big endian)
# [PRIO 2][SRC 5][DST 5][DPORT 6][SPORT 6][FLAGS 8]
# ---------------------------------------------------------------------------
def csp_header_unpack(raw4):
    h = struct.unpack(">I", raw4)[0]
    return {
        "prio": (h >> 30) & 0x3,
        "src": (h >> 25) & 0x1F,
        "dst": (h >> 20) & 0x1F,
        "dport": (h >> 14) & 0x3F,
        "sport": (h >> 8) & 0x3F,
        "flags": h & 0xFF,
    }


def csp_header_pack(prio, src, dst, dport, sport, flags=0):
    h = ((prio & 3) << 30) | ((src & 0x1F) << 25) | ((dst & 0x1F) << 20) \
        | ((dport & 0x3F) << 14) | ((sport & 0x3F) << 8) | (flags & 0xFF)
    return struct.pack(">I", h)


def cfp_fragment(src, dst, payload, header4, ident):
    """Pecah satu paket CSP menjadi daftar (can_id, data) sesuai csp_can_tx()."""
    length = len(payload)
    frames = []
    first = header4 + struct.pack(">H", length) + payload[:2]
    remain = (length + CFP_OVERHEAD - 1) // 8
    frames.append((cfp_make_id(src, dst, CFP_BEGIN, remain, ident), first))
    sent = min(length, 2)
    while sent < length:
        chunk = payload[sent:sent + 8]
        remain = (length - sent - len(chunk) + 7) // 8
        frames.append((cfp_make_id(src, dst, CFP_MORE, remain, ident), chunk))
        sent += len(chunk)
    return frames


class CfpReassembler:
    """Menyusun ulang frame CFP menjadi paket CSP (meniru csp_can_rx())."""

    def __init__(self, timeout=1.0):
        self.buffers = {}
        self.timeout = timeout

    def push(self, can_id, data):
        f = cfp_fields(can_id)
        key = (f["src"], f["dst"], f["id"])
        now = time.time()
        for k in [k for k, b in self.buffers.items() if now - b["t"] > self.timeout]:
            del self.buffers[k]

        if f["type"] == CFP_BEGIN:
            if len(data) < CFP_OVERHEAD:
                return None, "BEGIN terlalu pendek"
            hdr = csp_header_unpack(bytes(data[:4]))
            length = struct.unpack(">H", bytes(data[4:6]))[0]
            buf = {"hdr": hdr, "len": length, "data": bytearray(data[6:]),
                   "remain": f["remain"], "t": now}
            self.buffers[key] = buf
        else:
            buf = self.buffers.get(key)
            if buf is None:
                return None, "frame MORE tanpa BEGIN"
            if f["remain"] != buf["remain"] - 1:
                del self.buffers[key]
                return None, "frame hilang (remain tidak urut)"
            buf["remain"] = f["remain"]
            buf["data"] += bytes(data)

        if len(buf["data"]) >= buf["len"]:
            del self.buffers[key]
            return {"hdr": buf["hdr"], "data": bytes(buf["data"][:buf["len"]])}, None
        return None, None


# ---------------------------------------------------------------------------
# Node CSP sederhana di PC
# ---------------------------------------------------------------------------
class CspNode:
    def __init__(self, bus, addr=ADDR_PC, verbose=False):
        self.bus = bus
        self.addr = addr
        self.verbose = verbose
        self.rx = CfpReassembler()
        self.ident = 0
        self.sport = 20
        self.inbox = queue.Queue()
        self.stats = {"frames": 0, "packets": 0, "errors": 0}
        self._tx_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        self._thread.join(timeout=1)

    def _rx_loop(self):
        while not self._stop.is_set():
            try:
                msg = self.bus.recv(timeout=0.1)
            except Exception as e:  # noqa: BLE001  (mis. kabel USB dicabut)
                self.inbox.put(("fatal", str(e)))
                return
            if msg is None:
                continue
            if msg.is_error_frame:
                self.stats["errors"] += 1
                self.inbox.put(("error", msg))
                continue
            if not msg.is_extended_id:
                self.inbox.put(("std", msg))
                continue
            self.stats["frames"] += 1
            pkt, err = self.rx.push(msg.arbitration_id, msg.data)
            self.inbox.put(("frame", msg, err))
            if pkt:
                pkt["t"] = time.time()
                self.stats["packets"] += 1
                self.inbox.put(("packet", pkt))

    def alloc_sport(self):
        self.sport = 17 + (self.sport - 16) % 40   # port sementara 17..56
        return self.sport

    def send(self, dst, dport, payload, sport=None, prio=2):
        if sport is None:
            sport = self.alloc_sport()
        hdr = csp_header_pack(prio, self.addr, dst, dport, sport)
        with self._tx_lock:   # serial slcan: satu pengirim pada satu waktu
            self.ident = (self.ident + 1) & 0x3FF
            for can_id, data in cfp_fragment(self.addr, dst, payload, hdr, self.ident):
                self.bus.send(can.Message(arbitration_id=can_id, data=data,
                                          is_extended_id=True), timeout=0.2)
        return sport

    def wait_reply(self, src, sport, timeout):
        """Tunggu paket dari node 'src' yang ditujukan ke port 'sport' kita."""
        end = time.time() + timeout
        while time.time() < end:
            try:
                item = self.inbox.get(timeout=max(0.0, end - time.time()))
            except queue.Empty:
                break
            if item[0] == "packet":
                h = item[1]["hdr"]
                if h["src"] == src and h["dst"] == self.addr and h["dport"] == sport:
                    return item[1]
        return None

    def transaction(self, dst, dport, payload, timeout=1.0):
        t0 = time.time()
        sport = self.send(dst, dport, payload)
        reply = self.wait_reply(dst, sport, timeout)
        return reply, (time.time() - t0) * 1000.0


# ---------------------------------------------------------------------------
# Tampilan
# ---------------------------------------------------------------------------
def node_name(a):
    return f"{NODE_NAMES.get(a, '?')}({a})"


def describe_packet(pkt):
    h, d = pkt["hdr"], pkt["data"]
    port = PORT_NAMES.get(h["dport"]) or (PORT_NAMES.get(h["sport"], str(h["dport"])) + " balasan")
    line = (f"CSP {node_name(h['src'])}:{h['sport']} -> {node_name(h['dst'])}:{h['dport']} "
            f"[{port}] prio={h['prio']} len={len(d)}")
    extra = ""
    if h["dport"] == PORT_PING or h["sport"] == PORT_PING:
        extra = f"ping {len(d)} byte"
    elif h["dport"] == PORT_ECHO or h["sport"] == PORT_ECHO:
        extra = f'teks="{d.decode(errors="replace")}"'
    elif h["dport"] == PORT_TLM:
        extra = f"checksum={sum(d)}"
    elif h["src"] == ADDR_EPS and h["sport"] == PORT_EPS_HK and len(d) == EPS_HK_SIZE:
        extra = format_hk(d)
    elif h["dport"] == PORT_EPS_CMD and len(d) == 2:
        extra = f"perintah rail={d[0]} -> {'ON' if d[1] else 'OFF'}"
    elif h["sport"] == PORT_EPS_CMD and len(d) == 2:
        extra = f"status={'OK' if d[0] == 0 else 'DITOLAK'} rail={'ON' if d[1] else 'OFF'}"
    elif d:
        extra = "data=" + d[:16].hex(" ") + (" ..." if len(d) > 16 else "")
    return line + ("  " + extra if extra else "")


def format_hk(d):
    up, t10, vdda, rail, _, cnt, rxf, txf = struct.unpack(EPS_HK_FMT, d)
    return (f"uptime={up}s suhu={t10 / 10:.1f}C VDDA={vdda}mV payload={'ON' if rail else 'OFF'} "
            f"HK#{cnt} CAN rx={rxf} tx={txf}")


# ---------------------------------------------------------------------------
# Koneksi ke CANable (slcan)
# ---------------------------------------------------------------------------
def find_canable_ports():
    """Daftar port COM; port CANable (VID 16D0) diletakkan paling depan."""
    if list_ports is None:
        return []
    canable, others = [], []
    for p in list_ports.comports():
        desc = (p.description or "") + " " + (p.product or "")
        if (p.vid == CANABLE_SLCAN_VID and p.pid == CANABLE_SLCAN_PID) or "canable" in desc.lower():
            canable.append(p.device)
        else:
            others.append(p.device)
    return canable + others


def open_bus(args):
    if args.interface == "virtual":
        return can.Bus(interface="virtual", channel=args.channel or "csp")
    if args.interface == "slcan":
        port = args.channel
        if not port:
            ports = find_canable_ports()
            if not ports:
                raise RuntimeError("Port COM CANable tidak ditemukan (cek kabel USB / pyserial).")
            port = ports[0]
        # CANable memakai USB CDC: tty_baudrate tidak berpengaruh,
        # bitrate CAN dikirim sebagai perintah slcan (S8 = 1 Mbit/s).
        return can.Bus(interface="slcan", channel=port, bitrate=args.bitrate)
    kw = {"interface": args.interface, "bitrate": args.bitrate}
    if args.channel:
        kw["channel"] = args.channel
    return can.Bus(**kw)


# ---------------------------------------------------------------------------
# Perintah
# ---------------------------------------------------------------------------
def cmd_list(args):
    ports = find_canable_ports()
    if list_ports is None:
        print("pyserial belum terpasang: pip install pyserial")
        return
    if not ports:
        print("Tidak ada port COM. Cek kabel USB dan firmware CANable (harus slcan).")
    for p in list_ports.comports():
        tag = "  <- CANable" if p.vid == CANABLE_SLCAN_VID else ""
        print(f"{p.device:8s} {p.description}{tag}")


def cmd_monitor(args):
    bus = open_bus(args)
    node = CspNode(bus)
    print(f"Monitor CAN {args.bitrate} bit/s. Tekan Ctrl+C untuk berhenti.\n")
    t_last = time.time()
    try:
        while True:
            try:
                item = node.inbox.get(timeout=1.0)
            except queue.Empty:
                item = None
            ts = time.strftime("%H:%M:%S")
            if item:
                kind = item[0]
                if kind == "frame" and args.frames:
                    msg, err = item[1], item[2]
                    f = cfp_fields(msg.arbitration_id)
                    print(f"{ts} frame 0x{msg.arbitration_id:08X} "
                          f"src={f['src']} dst={f['dst']} {'BEGIN' if f['type'] == 0 else 'MORE '} "
                          f"remain={f['remain']:3d} id={f['id']:4d} | {msg.data.hex(' ')}"
                          + (f"  !! {err}" if err else ""))
                elif kind == "packet":
                    print(f"{ts} {describe_packet(item[1])}")
                elif kind == "error":
                    print(f"{ts} ERROR FRAME {item[1]}")
                elif kind == "std":
                    m = item[1]
                    print(f"{ts} frame standar 0x{m.arbitration_id:03X} {m.data.hex(' ')} (bukan CFP)")
                elif kind == "fatal":
                    print(f"{ts} koneksi ke adapter terputus: {item[1]}")
                    break
            if time.time() - t_last >= 10:
                t_last = time.time()
                s = node.stats
                print(f"--- statistik: frame={s['frames']} paket CSP={s['packets']} error={s['errors']}")
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        bus.shutdown()


def cmd_ping(args):
    bus = open_bus(args)
    node = CspNode(bus)
    try:
        for i in range(args.count):
            payload = bytes(range(args.size))
            reply, ms = node.transaction(args.addr, PORT_PING, payload, args.timeout)
            if reply and reply["data"] == payload:
                print(f"ping {node_name(args.addr)} #{i}: {ms:.1f} ms ({args.size} byte)")
            elif reply:
                print(f"ping {node_name(args.addr)} #{i}: balasan berbeda ({len(reply['data'])} byte)")
            else:
                print(f"ping {node_name(args.addr)} #{i}: TIMEOUT")
            time.sleep(0.5)
    finally:
        node.close()
        bus.shutdown()


def cmd_hk(args):
    bus = open_bus(args)
    node = CspNode(bus)
    try:
        reply, ms = node.transaction(ADDR_EPS, PORT_EPS_HK, b"\x00", args.timeout)
        if reply and len(reply["data"]) == EPS_HK_SIZE:
            print(f"EPS housekeeping ({ms:.1f} ms): {format_hk(reply['data'])}")
        else:
            print("Housekeeping EPS: TIMEOUT / format salah")
    finally:
        node.close()
        bus.shutdown()


def cmd_payload(args):
    bus = open_bus(args)
    node = CspNode(bus)
    try:
        on = 1 if args.state == "on" else 0
        reply, ms = node.transaction(ADDR_EPS, PORT_EPS_CMD, bytes([0, on]), args.timeout)
        if reply and len(reply["data"]) == 2:
            st, rail = reply["data"]
            print(f"Perintah payload {args.state.upper()}: {'OK' if st == 0 else 'DITOLAK'}, "
                  f"rail sekarang {'ON' if rail else 'OFF'} ({ms:.1f} ms)")
        else:
            print("Perintah payload: TIMEOUT")
    finally:
        node.close()
        bus.shutdown()


def cmd_echo(args):
    bus = open_bus(args)
    node = CspNode(bus)
    try:
        reply, ms = node.transaction(args.addr, PORT_ECHO, args.text.encode(), args.timeout)
        if reply:
            print(f'Balasan {node_name(args.addr)} ({ms:.1f} ms): "{reply["data"].decode(errors="replace")}"')
        else:
            print("Echo: TIMEOUT")
    finally:
        node.close()
        bus.shutdown()


def main():
    p = argparse.ArgumentParser(description="Alat uji CSP lewat CAN (Makerbase CANable V2.0 Pro)")
    p.add_argument("--interface", default="slcan", help="slcan (default), virtual, dll")
    p.add_argument("--channel", default=None, help="port COM CANable, mis. COM7 (opsional)")
    p.add_argument("--bitrate", type=int, default=1000000, help="default 1000000 (1 Mbit/s)")
    p.add_argument("--timeout", type=float, default=1.0)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="tampilkan port COM / CANable").set_defaults(fn=cmd_list)

    m = sub.add_parser("monitor", help="tampilkan lalu lintas bus")
    m.add_argument("--frames", action="store_true", help="tampilkan juga setiap frame CAN")
    m.set_defaults(fn=cmd_monitor)

    pg = sub.add_parser("ping", help="ping node CSP")
    pg.add_argument("addr", type=int, help="1 = OBC, 2 = EPS")
    pg.add_argument("--count", type=int, default=4)
    pg.add_argument("--size", type=int, default=16)
    pg.set_defaults(fn=cmd_ping)

    sub.add_parser("hk", help="minta housekeeping EPS").set_defaults(fn=cmd_hk)

    pl = sub.add_parser("payload", help="ON/OFF rail payload EPS")
    pl.add_argument("state", choices=["on", "off"])
    pl.set_defaults(fn=cmd_payload)

    e = sub.add_parser("echo", help="kirim teks ke port 10")
    e.add_argument("addr", type=int)
    e.add_argument("text")
    e.set_defaults(fn=cmd_echo)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
