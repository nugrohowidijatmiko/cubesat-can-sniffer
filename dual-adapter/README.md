[English](README.en.md) | **Bahasa Indonesia**

# Versi dua adapter: Korlan USB2CAN + Makerbase CANable

Satu program untuk kedua adapter. GUI dan alat command line mendeteksi **Korlan USB2CAN** (8devices) dan **Makerbase CANable V2.0 / V2.0 Pro** (firmware slcan) secara otomatis, dan adapter bisa dipilih atau diganti tanpa mengubah kode. Logika CFP/CSP dan mode simulasi sama dengan folder utama.

Tutorial terkait:
- Korlan: https://nugrohowidijatmiko.blogspot.com/2026/10/sniffing-can-bus-cubesat-libcsp-dengan.html
- CANable: https://nugrohowidijatmiko.blogspot.com/2026/11/sniffing-can-bus-cubesat-libcsp-dengan.html

## Isi folder

| File | Fungsi |
|---|---|
| `csp_can_tool.py` | Library CFP/CSP + deteksi adapter + alat command line (`list`, `monitor`, `ping`, `hk`, `payload`, `echo`), interface default `auto` |
| `csp_can_gui.py` | GUI Tkinter dengan pilihan *Adapter* `otomatis` / `usb2can` / `slcan` / `simulasi` dan daftar *Perangkat* yang terdeteksi |

## Persiapan

```bash
pip install python-can pyserial pywin32
```

- **Korlan:** pasang driver WinUSB 8devices dan salin `usb2can.dll` (x64) ke folder ini. `pywin32` dipakai untuk membaca serial number Korlan.
- **CANable:** firmware slcan (muncul sebagai port COM), pakai kabel USB-C data. Tidak perlu driver atau DLL.

Kedua adapter boleh tercolok bersamaan, dan boleh juga dipasang paralel di bus yang sama.

## Menjalankan

```bash
python csp_can_tool.py list
python csp_can_gui.py
```

Contoh hasil `list` dengan kedua adapter terpasang:

```
usb2can  04EF18C4   Korlan USB2CAN  S/N 04EF18C4
slcan    COM3       CANable  COM3
slcan    COM6       COM6  (STMicroelectronics STLink Virtual COM Port (COM6))   (bukan adapter yang dikenali)
```

Di GUI:

- **Adapter `otomatis`** (bawaan): tombol **Cari** mengisi daftar **Perangkat** dengan semua adapter, misalnya `Korlan USB2CAN  S/N 04EF18C4` dan `CANable  COM3`. Adapter pertama yang dikenali langsung dipilih; kalau keduanya ada, Korlan diutamakan.
- **`usb2can` / `slcan`**: daftar hanya menampilkan jenis itu.
- Nilai di kolom Perangkat juga boleh diketik manual: `COM3` dianggap CANable, `04EF18C4` dianggap serial number Korlan.
- Status bar menampilkan adapter yang dipakai, misalnya *TERHUBUNG 1000 kbit/s · Korlan S/N 04EF18C4*.

Command line memilih adapter otomatis, atau bisa dipaksa:

```bash
python csp_can_tool.py monitor --frames
python csp_can_tool.py --interface usb2can --channel 04EF18C4 ping 2
python csp_can_tool.py --interface slcan --channel COM3 hk
```

## Kondisi bus dan error

| Adapter | Baris *Kondisi bus* |
|---|---|
| Korlan | Jenis error dibaca dari kode status adapter: stuff error, form error, ACK error, CRC error, bus warning, error passive, BUS-OFF |
| CANable | Firmware slcan tidak melaporkan jenis error, jadi kondisi ditebak dari lalu lintas: **OK** atau **DIAM: tidak ada frame** |

Langkah troubleshooting lengkap ada di [README utama](../README.md) (Korlan) dan [canable/README.md](../canable/README.md) (CANable).
