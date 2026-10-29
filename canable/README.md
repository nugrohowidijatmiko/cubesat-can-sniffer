[English](README.en.md) | **Bahasa Indonesia**

# Versi Makerbase CANable V2.0 Pro (slcan)

Folder ini berisi versi sniffer yang memakai **Makerbase CANable V2.0 Pro** sebagai pengganti Korlan USB2CAN. Logika CFP/CSP, GUI, dan mode simulasi sama dengan versi Korlan di folder utama; yang berubah hanya cara terhubung ke adapter.

Tutorial: *Sniffing CAN Bus CubeSat (libcsp) dengan Makerbase CANable V2.0 Pro dan GUI Python* di [nugrohowidijatmiko.blogspot.com](https://nugrohowidijatmiko.blogspot.com/).

## Isi folder

| File | Fungsi |
|---|---|
| `csp_can_tool.py` | Library CFP/CSP + alat command line (`list`, `monitor`, `ping`, `hk`, `payload`, `echo`), interface default `slcan` |
| `csp_can_gui.py` | GUI Tkinter: pilih *Adapter* `slcan` dan *Port* COM CANable, atau `simulasi` tanpa hardware |
| `test_canable.py` | Tes koneksi singkat: tampilkan port COM lalu frame CAN selama 5 detik |

## Perbedaan dengan versi Korlan

| | Korlan USB2CAN | Makerbase CANable V2.0 Pro |
|---|---|---|
| Konektor | DB9 | Terminal sekrup CANH / CANL / GND |
| Isolasi | Tidak | Ya (galvanik) |
| Terminator 120 Ω | Tidak ada | Ada di board, bisa ON/OFF |
| Driver Windows | WinUSB + `usb2can.dll` | Tidak perlu (firmware slcan = port COM) |
| python-can | `interface="usb2can"` | `interface="slcan"` |
| Laporan jenis error bus | Ada (stuff, ACK, CRC, dll.) | Tidak ada di firmware slcan |

## Langkah singkat

1. **Cek firmware.** Colokkan CANable dan buka Device Manager. Firmware **slcan** muncul sebagai port COM (misalnya COM7). Kalau muncul sebagai perangkat "candleLight", ganti firmware ke *CANable 2.0 slcan* lewat [canable.io/updater](https://canable.io/updater/) (Chrome, board dalam mode boot/DFU).
2. **Library Python.**
   ```bash
   pip install python-can pyserial
   ```
3. **Sambungkan CANable ke bus** secara paralel di tengah bus: CANH–CANH, CANL–CANL, GND–GND board. **Matikan terminator 120 Ω di CANable**, karena terminator hanya di kedua ujung bus (modul OBC dan EPS). Saat semua board mati, hambatan CANH–CANL harus sekitar 60 Ω; kalau sekitar 40 Ω, terminator CANable masih ON.
4. **Tes koneksi** (ganti `COM7` dengan port Anda):
   ```bash
   python test_canable.py
   ```
5. **Jalankan GUI.**
   ```bash
   python csp_can_gui.py
   ```
   Pilih *Adapter* `slcan`, pastikan *Port* berisi port COM CANable (tombol **Cari** mencari ulang; port dengan VID `16D0` otomatis dipilih), lalu klik **Hubungkan**.

### Tanpa GUI

```bash
python csp_can_tool.py list
python csp_can_tool.py --channel COM7 monitor --frames
python csp_can_tool.py --channel COM7 ping 2
python csp_can_tool.py hk
python csp_can_tool.py payload on
python csp_can_tool.py echo 1 "Halo OBC"
```

Tanpa `--channel`, port CANable dicari otomatis. Opsi lain: `--interface` (default `slcan`, bisa `virtual`), `--bitrate` (default 1000000), `--timeout`.

## Troubleshooting

Firmware slcan tidak melaporkan jenis error bus. Baris **Kondisi bus** di GUI menampilkan **OK** kalau ada frame dalam 3 detik terakhir, atau **DIAM: tidak ada frame** kalau bus diam.

| Gejala | Kemungkinan penyebab | Solusi |
|---|---|---|
| Tidak ada port COM baru | Firmware candleLight, kabel USB hanya untuk charging | Ganti firmware ke slcan, pakai kabel USB data |
| "could not open port" / "Access is denied" | Port COM sedang dipakai program lain | Tutup program lain, cabut-colok CANable |
| Kondisi bus "DIAM", frame CAN = 0 | CANH/CANL tertukar atau belum tersambung, bitrate berbeda, GND tidak tersambung | Cek wiring, GND bersama, samakan bitrate 1 Mbit/s |
| Frame hilang / error susun CFP | Terminator CANable masih ON (±40 Ω) atau tanpa terminator | Matikan terminator CANable, pasang 2×120 Ω di ujung bus |
| Error terus walau kabel benar | MCP2551 dicatu 5 V butuh TXD ≥ 3,5 V, STM32 hanya 3,3 V | Pakai SN65HVD230 atau pull-up 2,2 kΩ CTX ke 5 V + PA12 open-drain |

Dalam mode normal CANable ikut memberi ACK, jadi satu board saja bersama CANable tetap terbaca.
