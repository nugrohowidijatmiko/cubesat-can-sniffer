#!/usr/bin/env python3
"""
csp_can_gui.py - GUI pemantau bus CAN CubeSat (libcsp 1.6 / CFP)
untuk Makerbase CANable V2.0 Pro (firmware slcan) + python-can.

Jalankan: python csp_can_gui.py
Butuh   : pip install python-can pyserial

Fitur:
- Hubungkan ke CANable lewat port COM (atau mode Simulasi tanpa hardware)
- Tabel paket CSP yang sudah disusun ulang (warna per node)
- Tabel frame CAN mentah (ID CFP diuraikan)
- Panel EPS: suhu, VDDA, status payload, uptime (auto-refresh)
- Tombol Ping OBC / Ping EPS, Minta HK, Payload ON/OFF, kirim pesan
- Statistik bus + simpan log ke CSV
"""
import csv
import queue
import struct
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import can

import csp_can_tool as T

APP_TITLE = "CubeSat CAN Monitor - Makerbase CANable V2.0 Pro"
MAX_ROWS = 2000
SILENT_WARN_S = 3.0   # bus dianggap diam bila tidak ada frame selama ini

NODE_COLORS = {T.ADDR_OBC: "#1f5fd6", T.ADDR_EPS: "#c0392b", T.ADDR_PC: "#1a8a3a"}


# ---------------------------------------------------------------------------
# Simulator OBC + EPS (mode tanpa hardware, memakai bus 'virtual' python-can)
# ---------------------------------------------------------------------------
class Simulator:
    def __init__(self, channel):
        self.bus = can.Bus(interface="virtual", channel=channel)
        self.rx = T.CfpReassembler()
        self.ident = 0
        self.rail = 0
        self.hk_count = 0
        self.t0 = time.time()
        self.stop = threading.Event()
        threading.Thread(target=self._rx, daemon=True).start()
        threading.Thread(target=self._obc, daemon=True).start()

    def close(self):
        self.stop.set()
        time.sleep(0.15)
        self.bus.shutdown()

    def _send(self, src, dst, dport, sport, data):
        self.ident = (self.ident + 1) & 0x3FF
        hdr = T.csp_header_pack(2, src, dst, dport, sport)
        for cid, d in T.cfp_fragment(src, dst, data, hdr, self.ident):
            self.bus.send(can.Message(arbitration_id=cid, data=d, is_extended_id=True))
            time.sleep(0.0002)

    def _hk(self):
        temp = int(380 + 15 * ((time.time() * 0.2) % 1))
        return struct.pack(T.EPS_HK_FMT, int(time.time() - self.t0), temp, 3290,
                           self.rail, 0, self.hk_count, 0, 0)

    def _reply(self, node, pkt):
        h, d = pkt["hdr"], pkt["data"]
        if h["dport"] == T.PORT_PING:
            out = d
        elif h["dport"] == T.PORT_ECHO:
            out = f"ACK dari node {node} ({T.NODE_NAMES[node]})".encode()
        elif h["dport"] == T.PORT_TLM:
            return
        elif node == T.ADDR_EPS and h["dport"] == T.PORT_EPS_HK:
            self.hk_count += 1
            out = self._hk()
        elif node == T.ADDR_EPS and h["dport"] == T.PORT_EPS_CMD and len(d) == 2:
            self.rail = 1 if d[1] else 0
            out = bytes([0, self.rail])
        else:
            return
        self._send(node, h["src"], h["sport"], h["dport"], out)

    def _rx(self):
        while not self.stop.is_set():
            m = self.bus.recv(0.05)
            if m is None or not m.is_extended_id:
                continue
            pkt, _ = self.rx.push(m.arbitration_id, m.data)
            if pkt and pkt["hdr"]["dst"] in (T.ADDR_OBC, T.ADDR_EPS):
                self._reply(pkt["hdr"]["dst"], pkt)

    def _obc(self):
        """OBC tiruan: tiap 2 detik ping, HK dan paket 200 byte ke EPS."""
        n = 0
        while not self.stop.wait(2.0):
            self._send(T.ADDR_OBC, T.ADDR_EPS, T.PORT_PING, 30, bytes(range(32)))
            self._send(T.ADDR_EPS, T.ADDR_OBC, 30, T.PORT_PING, bytes(range(32)))
            self._send(T.ADDR_OBC, T.ADDR_EPS, T.PORT_EPS_HK, 31, b"\x00")
            self.hk_count += 1
            self._send(T.ADDR_EPS, T.ADDR_OBC, 31, T.PORT_EPS_HK, self._hk())
            self._send(T.ADDR_OBC, T.ADDR_EPS, T.PORT_TLM, 32, bytes((i + n) & 0xFF for i in range(200)))
            n += 1


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1280x800")
        self.minsize(1000, 640)

        self.bus = None
        self.node = None
        self.sim = None
        self.pending = {}          # sport -> (kind, dst, info, t0, deadline)
        self.log_rows = []         # untuk simpan CSV
        self.node_seen = {T.ADDR_OBC: 0.0, T.ADDR_EPS: 0.0}
        self.rate_count = 0
        self.rate_t = time.time()
        self.err_new = 0
        self.err_log_t = 0.0
        self.bus_err_t = 0.0
        self.last_frame_t = 0.0
        self.connect_t = 0.0
        self.send_errors = []

        self._style()
        self._build()
        self.after(40, self._poll)
        self.after(2000, self._auto_hk)
        self.after(300, lambda: self._scan_ports(quiet=True))
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------------- style
    def _style(self):
        import tkinter.font as tkfont
        fams = set(tkfont.families(self))
        ui = next((f for f in ("Segoe UI", "Helvetica", "DejaVu Sans", "Arial") if f in fams), "TkDefaultFont")
        mono = next((f for f in ("Consolas", "DejaVu Sans Mono", "Courier New") if f in fams), "TkFixedFont")
        self.ui_font, self.mono_font = ui, mono
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        self.configure(bg="#eef1f5")
        s.configure(".", font=(ui, 10), background="#eef1f5")
        s.configure("Card.TFrame", background="white", relief="flat")
        s.configure("Card.TLabel", background="white")
        s.configure("Title.TLabel", font=(ui, 11, "bold"), background="white")
        s.configure("Big.TLabel", font=(ui, 22, "bold"), background="white")
        s.configure("Unit.TLabel", font=(ui, 9), foreground="#666", background="white")
        s.configure("Treeview", rowheight=22, font=(mono, 10))
        s.configure("Treeview.Heading", font=(ui, 10, "bold"))
        s.configure("Accent.TButton", font=(ui, 10, "bold"))

    def _card(self, parent, title):
        f = ttk.Frame(parent, style="Card.TFrame", padding=10)
        ttk.Label(f, text=title, style="Title.TLabel").pack(anchor="w", pady=(0, 6))
        return f

    # ---------------------------------------------------------------- layout
    def _build(self):
        # ---- baris koneksi
        top = ttk.Frame(self, padding=(10, 8))
        top.pack(fill="x")
        ttk.Label(top, text="Adapter:").pack(side="left")
        self.var_if = tk.StringVar(value="slcan")
        ttk.Combobox(top, textvariable=self.var_if, width=10, state="readonly",
                     values=["slcan", "simulasi"]).pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Port:").pack(side="left")
        self.var_ch = tk.StringVar()
        self.cb_ch = ttk.Combobox(top, textvariable=self.var_ch, width=11)
        self.cb_ch.pack(side="left", padx=(4, 2))
        ttk.Button(top, text="Cari", width=5, command=self._scan_ports).pack(side="left", padx=(0, 12))
        ttk.Label(top, text="Bitrate:").pack(side="left")
        self.var_br = tk.StringVar(value="1000000")
        ttk.Combobox(top, textvariable=self.var_br, width=9,
                     values=["1000000", "500000", "250000", "125000"]).pack(side="left", padx=(4, 12))
        self.btn_conn = ttk.Button(top, text="Hubungkan", style="Accent.TButton", command=self._toggle)
        self.btn_conn.pack(side="left")
        self.lbl_status = tk.Label(top, text="  TIDAK TERHUBUNG  ", bg="#999", fg="white",
                                   font=(self.ui_font, 10, "bold"))
        self.lbl_status.pack(side="left", padx=12)
        ttk.Button(top, text="Simpan log CSV", command=self._save_csv).pack(side="right")
        ttk.Button(top, text="Bersihkan", command=self._clear).pack(side="right", padx=6)

        body = ttk.Frame(self, padding=(10, 0, 10, 10))
        body.pack(fill="both", expand=True)

        # ---- panel kiri
        left = ttk.Frame(body, width=330)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        # node status
        c = self._card(left, "Status node")
        c.pack(fill="x", pady=(0, 8))
        self.node_lbl = {}
        for addr in (T.ADDR_OBC, T.ADDR_EPS):
            row = ttk.Frame(c, style="Card.TFrame")
            row.pack(fill="x", pady=2)
            dot = tk.Label(row, text="●", fg="#bbb", bg="white", font=(self.ui_font, 14))
            dot.pack(side="left")
            ttk.Label(row, text=f"{T.NODE_NAMES[addr]}  (alamat {addr})", style="Card.TLabel",
                      width=16).pack(side="left")
            info = ttk.Label(row, text="belum terlihat", style="Card.TLabel", foreground="#777")
            info.pack(side="left")
            self.node_lbl[addr] = (dot, info)

        # EPS housekeeping
        c = self._card(left, "EPS housekeeping")
        c.pack(fill="x", pady=(0, 8))
        grid = ttk.Frame(c, style="Card.TFrame")
        grid.pack(fill="x")
        self.hk = {}
        for i, (key, label, unit) in enumerate([("temp", "Suhu chip", "°C"), ("vdda", "VDDA", "mV"),
                                                ("rail", "Payload", ""), ("uptime", "Uptime", "detik")]):
            f = ttk.Frame(grid, style="Card.TFrame", padding=(0, 2))
            f.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 18), pady=2)
            ttk.Label(f, text=label, style="Unit.TLabel").pack(anchor="w")
            v = ttk.Label(f, text="–", style="Big.TLabel")
            v.pack(anchor="w")
            ttk.Label(f, text=unit, style="Unit.TLabel").pack(anchor="w")
            self.hk[key] = v
        self.lbl_hk_time = ttk.Label(c, text="belum ada data", style="Unit.TLabel")
        self.lbl_hk_time.pack(anchor="w", pady=(4, 4))
        r = ttk.Frame(c, style="Card.TFrame")
        r.pack(fill="x")
        ttk.Button(r, text="Minta HK", command=self._req_hk).pack(side="left")
        self.var_auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(r, text="otomatis tiap 2 s", variable=self.var_auto).pack(side="left", padx=8)

        # perintah
        c = self._card(left, "Perintah")
        c.pack(fill="x", pady=(0, 8))
        r = ttk.Frame(c, style="Card.TFrame")
        r.pack(fill="x", pady=2)
        ttk.Button(r, text="Ping OBC", command=lambda: self._ping(T.ADDR_OBC)).pack(side="left", expand=True, fill="x")
        ttk.Button(r, text="Ping EPS", command=lambda: self._ping(T.ADDR_EPS)).pack(side="left", expand=True, fill="x", padx=(6, 0))
        r = ttk.Frame(c, style="Card.TFrame")
        r.pack(fill="x", pady=2)
        ttk.Button(r, text="Payload ON", command=lambda: self._payload(1)).pack(side="left", expand=True, fill="x")
        ttk.Button(r, text="Payload OFF", command=lambda: self._payload(0)).pack(side="left", expand=True, fill="x", padx=(6, 0))
        r = ttk.Frame(c, style="Card.TFrame")
        r.pack(fill="x", pady=(6, 2))
        self.var_dst = tk.StringVar(value="EPS (2)")
        ttk.Combobox(r, textvariable=self.var_dst, width=8, state="readonly",
                     values=["OBC (1)", "EPS (2)"]).pack(side="left")
        self.var_msg = tk.StringVar(value="Halo dari PC")
        e = ttk.Entry(r, textvariable=self.var_msg)
        e.pack(side="left", fill="x", expand=True, padx=6)
        e.bind("<Return>", lambda _: self._echo())
        ttk.Button(r, text="Kirim", command=self._echo).pack(side="left")
        self.lbl_result = tk.Label(c, text="", bg="white", anchor="w", justify="left",
                                   font=(self.ui_font, 10), wraplength=300)
        self.lbl_result.pack(fill="x", pady=(6, 0))

        # statistik
        c = self._card(left, "Statistik bus")
        c.pack(fill="both", expand=True)
        self.stat_lbl = {}
        for key, label in [("frames", "Frame CAN"), ("packets", "Paket CSP"), ("rate", "Frame/detik"),
                           ("errors", "Error frame"), ("cfp_err", "Error susun CFP")]:
            row = ttk.Frame(c, style="Card.TFrame")
            row.pack(fill="x")
            ttk.Label(row, text=label, style="Card.TLabel").pack(side="left")
            v = ttk.Label(row, text="0", style="Card.TLabel", font=(self.ui_font, 10, "bold"))
            v.pack(side="right")
            self.stat_lbl[key] = v
        self.cfp_err = 0
        row = ttk.Frame(c, style="Card.TFrame")
        row.pack(fill="x", pady=(6, 0))
        ttk.Label(row, text="Kondisi bus", style="Card.TLabel").pack(side="left")
        self.lbl_bus = tk.Label(row, text="–", bg="white", font=(self.ui_font, 10, "bold"))
        self.lbl_bus.pack(side="right")

        # ---- panel kanan: tab
        nb = ttk.Notebook(body)
        nb.pack(side="left", fill="both", expand=True)

        t1 = ttk.Frame(nb)
        nb.add(t1, text="  Paket CSP  ")
        cols = ("time", "src", "dst", "port", "len", "info")
        self.tv_pkt = self._tree(t1, cols, {"time": ("Waktu", 95), "src": ("Dari", 90), "dst": ("Ke", 90),
                                            "port": ("Port", 110), "len": ("Len", 50), "info": ("Isi", 520)})
        for addr, col in NODE_COLORS.items():
            self.tv_pkt.tag_configure(f"n{addr}", foreground=col)

        t2 = ttk.Frame(nb)
        nb.add(t2, text="  Frame CAN  ")
        self.var_frames = tk.BooleanVar(value=True)
        ttk.Checkbutton(t2, text="Tampilkan frame (matikan jika bus sangat ramai)",
                        variable=self.var_frames).pack(anchor="w", padx=4, pady=2)
        cols = ("time", "id", "src", "dst", "type", "remain", "cfp", "dlc", "data")
        self.tv_frm = self._tree(t2, cols, {"time": ("Waktu", 95), "id": ("CAN ID", 95), "src": ("Src", 45),
                                            "dst": ("Dst", 45), "type": ("Tipe", 60), "remain": ("Remain", 60),
                                            "cfp": ("CFP id", 60), "dlc": ("DLC", 40), "data": ("Data", 300)})
        self.tv_frm.tag_configure("err", foreground="#c0392b")

        t3 = ttk.Frame(nb)
        nb.add(t3, text="  Log  ")
        self.txt_log = tk.Text(t3, font=(self.mono_font, 10), wrap="word", bg="#fbfbfb")
        self.txt_log.pack(fill="both", expand=True)

        self._log("Siap. Pilih port COM CANable lalu klik Hubungkan. Pilih 'simulasi' untuk mencoba tanpa hardware.")

    def _tree(self, parent, cols, spec):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tv = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            title, w = spec[c]
            tv.heading(c, text=title)
            tv.column(c, width=w, anchor="w", stretch=(c in ("info", "data")))
        sb = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return tv

    # ---------------------------------------------------------------- koneksi
    def _toggle(self):
        if self.bus:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        try:
            br = int(self.var_br.get())
            if self.var_if.get() == "simulasi":
                self.sim = Simulator("csp_sim")
                self.bus = can.Bus(interface="virtual", channel="csp_sim")
            else:
                if not self.var_ch.get().strip():
                    self._scan_ports(quiet=True)

                class A:  # argumen untuk open_bus()
                    pass
                a = A()
                a.interface, a.channel, a.bitrate = "slcan", (self.var_ch.get().strip() or None), br
                self.bus = T.open_bus(a)
            self.node = T.CspNode(self.bus)
        except Exception as e:  # noqa: BLE001
            self.bus = None
            if self.sim:
                self.sim.close()
                self.sim = None
            messagebox.showerror("Gagal terhubung",
                                 f"{e}\n\nCek: CANable memakai firmware slcan (muncul sebagai port COM), "
                                 "port COM benar dan tidak sedang dipakai program lain, "
                                 "serta python-can dan pyserial sudah terpasang.")
            return
        self.connect_t = time.time()
        self.last_frame_t = 0.0
        self.btn_conn.configure(text="Putuskan")
        port = "" if self.var_if.get() == "simulasi" else (self.var_ch.get().strip() or "auto")
        self.lbl_status.configure(text=f"  TERHUBUNG {int(self.var_br.get()) // 1000} kbit/s"
                                  + (f" · {port}" if port else "") + "  ", bg="#1a8a3a")
        self.title(f"{APP_TITLE}" + (f"  [{port}]" if port else ""))
        self._log(f"Terhubung ({self.var_if.get()}{', ' + port if port else ''}), alamat CSP PC = {T.ADDR_PC}")

    def _scan_ports(self, quiet=False):
        """Cari port COM; port CANable diletakkan paling depan."""
        if T.list_ports is None:
            if not quiet:
                self._log("pyserial belum terpasang: pip install pyserial")
            return []
        ports = T.find_canable_ports()
        self.cb_ch.configure(values=ports)
        canable = [p.device for p in T.list_ports.comports() if p.vid == T.CANABLE_SLCAN_VID]
        if ports:
            if self.var_ch.get().strip() not in ports:
                self.var_ch.set(ports[0])
            if canable:
                self._log("CANable terdeteksi di " + ", ".join(canable))
            elif not quiet:
                self._log("Port COM: " + ", ".join(ports) + " (CANable tidak dikenali otomatis, pilih manual)")
        elif not quiet:
            self._log("Tidak ada port COM (cek kabel USB dan firmware CANable harus slcan).")
        return ports

    def _disconnect(self):
        try:
            if self.node:
                self.node.close()
            if self.bus:
                self.bus.shutdown()
            if self.sim:
                self.sim.close()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self.node = self.bus = self.sim = None
            self.pending.clear()
            self.btn_conn.configure(text="Hubungkan")
            self.lbl_status.configure(text="  TIDAK TERHUBUNG  ", bg="#999")
            self.lbl_bus.configure(text="–", fg="black")
            self._log("Koneksi diputus")

    def _on_close(self):
        if self.bus:
            self._disconnect()
        self.destroy()

    # ---------------------------------------------------------------- perintah
    def _request(self, kind, dst, dport, payload, info=None, timeout=1.0):
        if not self.node:
            self._result("Belum terhubung ke adapter.", "#c0392b")
            return
        node = self.node
        sport = node.alloc_sport()
        self.pending[sport] = (kind, dst, info, time.time(), time.time() + timeout)

        def worker():
            # dikirim di thread terpisah agar GUI tidak macet bila adapter lambat
            try:
                node.send(dst, dport, payload, sport=sport)
            except Exception as e:  # noqa: BLE001
                self.send_errors.append(str(e))
        threading.Thread(target=worker, daemon=True).start()

    def _ping(self, addr):
        self._request("ping", addr, T.PORT_PING, bytes(range(16)), bytes(range(16)))

    def _req_hk(self):
        self._request("hk", T.ADDR_EPS, T.PORT_EPS_HK, b"\x00")

    def _payload(self, on):
        self._request("cmd", T.ADDR_EPS, T.PORT_EPS_CMD, bytes([0, on]), on)

    def _echo(self):
        dst = T.ADDR_OBC if self.var_dst.get().startswith("OBC") else T.ADDR_EPS
        self._request("echo", dst, T.PORT_ECHO, self.var_msg.get().encode())

    def _auto_hk(self):
        if self.node and self.var_auto.get():
            if not any(p[0] == "hk" for p in self.pending.values()):
                self._req_hk()
        self.after(2000, self._auto_hk)

    def _handle_reply(self, pkt):
        h = pkt["hdr"]
        p = self.pending.get(h["dport"])
        if not p or h["src"] != p[1] or h["dst"] != T.ADDR_PC:
            return
        del self.pending[h["dport"]]
        kind, dst, info, t0, _ = p
        ms = (pkt.get("t", time.time()) - t0) * 1000
        name = f"{T.NODE_NAMES[dst]} ({dst})"
        d = pkt["data"]
        if kind == "ping":
            ok = d == info
            self._result(f"Ping {name}: {ms:.1f} ms" + ("" if ok else "  (data berbeda!)"),
                         "#1a8a3a" if ok else "#c0392b")
        elif kind == "hk" and len(d) == T.EPS_HK_SIZE:
            self._show_hk(d, ms)
        elif kind == "cmd" and len(d) == 2:
            ok = d[0] == 0
            self._result(f"Payload {'ON' if d[1] else 'OFF'}: {'OK' if ok else 'DITOLAK'}  ({ms:.1f} ms)",
                         "#1a8a3a" if ok else "#c0392b")
        elif kind == "echo":
            self._result(f'Balasan {name} ({ms:.1f} ms):\n"{d.decode(errors="replace")}"', "#1f5fd6")

    def _show_hk(self, d, ms=None):
        up, t10, vdda, rail, _, cnt, rxf, txf = struct.unpack(T.EPS_HK_FMT, d)
        self.hk["temp"].configure(text=f"{t10 / 10:.1f}")
        self.hk["vdda"].configure(text=f"{vdda}")
        self.hk["rail"].configure(text="ON" if rail else "OFF", foreground="#1a8a3a" if rail else "#777")
        self.hk["uptime"].configure(text=f"{up}")
        extra = f", {ms:.0f} ms" if ms is not None else ""
        self.lbl_hk_time.configure(text=f"diperbarui {time.strftime('%H:%M:%S')}{extra} · HK #{cnt}")

    def _check_timeouts(self):
        now = time.time()
        for sport, p in list(self.pending.items()):
            if now > p[4]:
                del self.pending[sport]
                kind, dst = p[0], p[1]
                label = {"ping": "Ping", "hk": "Housekeeping", "cmd": "Perintah payload",
                         "echo": "Pesan"}[kind]
                self._result(f"{label} ke {T.NODE_NAMES[dst]} ({dst}): TIMEOUT", "#c0392b")
                self._log(f"{label} ke node {dst}: timeout")

    # ---------------------------------------------------------------- loop GUI
    def _poll(self):
        if self.node:
            n = 0
            while n < 500 and self.node:
                try:
                    item = self.node.inbox.get_nowait()
                except queue.Empty:
                    break
                n += 1
                self._handle_item(item)
            if self.node:
                self._check_timeouts()
                self._update_stats()
        self.after(40, self._poll)

    def _handle_item(self, item):
        ts = time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"
        kind = item[0]
        if kind == "frame":
            msg, err = item[1], item[2]
            self.rate_count += 1
            self.last_frame_t = time.time()
            f = T.cfp_fields(msg.arbitration_id)
            if f["src"] in self.node_seen:
                self.node_seen[f["src"]] = time.time()
            if err:
                self.cfp_err += 1
                self._log(f"CFP: {err} (ID 0x{msg.arbitration_id:08X})")
            if self.var_frames.get():
                self._insert(self.tv_frm, (ts, f"0x{msg.arbitration_id:08X}", f["src"], f["dst"],
                                           "BEGIN" if f["type"] == 0 else "MORE", f["remain"], f["id"],
                                           len(msg.data), msg.data.hex(" ")), ("err",) if err else ())
        elif kind == "packet":
            pkt = item[1]
            h = pkt["hdr"]
            desc = T.describe_packet(pkt)
            info = desc.split("  ", 1)[1] if "  " in desc else ""
            if h["dport"] in T.PORT_NAMES:
                port = f"{h['dport']} {T.PORT_NAMES[h['dport']]}"
            elif h["sport"] in T.PORT_NAMES:
                port = f"{h['dport']} re:{T.PORT_NAMES[h['sport']]}"
            else:
                port = str(h["dport"])
            self._insert(self.tv_pkt, (ts, f"{T.NODE_NAMES.get(h['src'], '?')}:{h['sport']}",
                                       f"{T.NODE_NAMES.get(h['dst'], '?')}:{h['dport']}", port,
                                       len(pkt["data"]), info), (f"n{h['src']}",))
            self.log_rows.append([ts, h["src"], h["sport"], h["dst"], h["dport"], len(pkt["data"]),
                                  pkt["data"].hex(), info])
            # HK EPS (dari siapa pun yang meminta, termasuk OBC) -> perbarui panel
            if h["src"] == T.ADDR_EPS and h["sport"] == T.PORT_EPS_HK and len(pkt["data"]) == T.EPS_HK_SIZE:
                self._show_hk(pkt["data"])
            self._handle_reply(pkt)
        elif kind == "error":
            # firmware slcan umumnya tidak mengirim error frame; kalau ada, hitung saja
            self.err_new += 1
        elif kind == "std":
            m = item[1]
            self._log(f"Frame standar 0x{m.arbitration_id:03X} {m.data.hex(' ')} (bukan CFP)")
        elif kind == "fatal":
            self._log(f"Koneksi ke adapter terputus: {item[1]}")
            messagebox.showerror("Adapter terputus", f"{item[1]}\n\nCek kabel USB CANable.")
            self._disconnect()

    def _insert(self, tv, values, tags=()):
        tv.insert("", "end", values=values, tags=tags)
        kids = tv.get_children()
        if len(kids) > MAX_ROWS:
            tv.delete(*kids[:len(kids) - MAX_ROWS])
        tv.yview_moveto(1.0)

    def _update_bus_label(self, now):
        """slcan tidak melaporkan jenis error, jadi kondisi bus ditebak dari lalu lintas."""
        if self.err_new and now - self.err_log_t >= 1.0:
            self.err_log_t = now
            self._log(f"Error frame dari adapter (1 detik terakhir): {self.err_new}")
            self.err_new = 0
            self.bus_err_t = now
            self.lbl_bus.configure(text="ERROR frame", fg="#c0392b")
        elif now - self.bus_err_t < 3:
            return
        elif self.last_frame_t and now - self.last_frame_t < SILENT_WARN_S:
            self.lbl_bus.configure(text="OK", fg="#1a8a3a")
        elif now - self.connect_t >= SILENT_WARN_S:
            self.lbl_bus.configure(text="DIAM: tidak ada frame", fg="#e67e22")

    def _update_stats(self):
        now = time.time()
        while self.send_errors:
            self._result(f"Gagal kirim: {self.send_errors.pop()}", "#c0392b")
        self._update_bus_label(now)
        s = self.node.stats
        self.stat_lbl["frames"].configure(text=str(s["frames"]))
        self.stat_lbl["packets"].configure(text=str(s["packets"]))
        self.stat_lbl["errors"].configure(text=str(s["errors"]))
        self.stat_lbl["cfp_err"].configure(text=str(self.cfp_err))
        if now - self.rate_t >= 1.0:
            self.stat_lbl["rate"].configure(text=f"{self.rate_count / (now - self.rate_t):.0f}")
            self.rate_count, self.rate_t = 0, now
        for addr, (dot, info) in self.node_lbl.items():
            seen = self.node_seen[addr]
            if seen == 0:
                continue
            age = now - seen
            if age < 5:
                dot.configure(fg="#1a8a3a")
                info.configure(text="aktif", foreground="#1a8a3a")
            else:
                dot.configure(fg="#e67e22")
                info.configure(text=f"diam {age:.0f} s", foreground="#e67e22")

    # ---------------------------------------------------------------- util
    def _result(self, text, color="#333"):
        self.lbl_result.configure(text=text, fg=color)

    def _log(self, text):
        self.txt_log.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.txt_log.see("end")

    def _clear(self):
        for tv in (self.tv_pkt, self.tv_frm):
            tv.delete(*tv.get_children())
        self.log_rows.clear()
        self.txt_log.delete("1.0", "end")

    def _save_csv(self):
        if not self.log_rows:
            messagebox.showinfo("Simpan log", "Belum ada paket CSP untuk disimpan.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            initialfile=time.strftime("csp_log_%Y%m%d_%H%M%S.csv"),
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["waktu", "src", "sport", "dst", "dport", "len", "data_hex", "keterangan"])
            w.writerows(self.log_rows)
        self._log(f"Log disimpan: {path}")


if __name__ == "__main__":
    App().mainloop()
