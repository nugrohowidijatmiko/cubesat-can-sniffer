[English](README.en.md) | **Bahasa Indonesia**

# Driver dan firmware adapter

Salinan cadangan file driver dan firmware yang dipakai di repo ini, supaya tetap tersedia walaupun file di situs pembuatnya dipindah atau dihapus. Semua file disalin apa adanya dari paket resmi pembuatnya, tanpa diubah.

> **Hak cipta:** file di folder ini milik pembuatnya masing-masing (8devices, Makerbase / CANable, ImpulseRC) dan **tidak** termasuk lisensi MIT repo ini. Kalau versi resmi masih tersedia, sebaiknya unduh dari sumber aslinya (tautan di bawah).

## Korlan USB2CAN (8devices) – `korlan/`

| File | Isi |
|---|---|
| `usb2can_winusb.msi` | Driver WinUSB untuk Windows. Jalankan sebagai Administrator; setelahnya Korlan muncul sebagai **USB2CAN** di Device Manager |
| `usb2can_canal_v2.0.0.zip` | USB2CAN CANAL DLL v2.0.0: `x64/Release/usb2can.dll` (Python 64-bit) dan `x86/Release/usb2can.dll` (Python 32-bit) |

Pemakaian: pasang driver, lalu salin `x64/Release/usb2can.dll` dari zip ke folder program (folder utama atau `dual-adapter/`). Sumber asli: halaman produk Korlan USB2CAN di 8devices, bagian *Resources*: https://wiki.8devices.com/korlan

## Makerbase CANable V2.0 / V2.0 Pro – `canable/`

Di Windows 10/11 dengan firmware **slcan**, CANable **tidak butuh driver** (muncul sebagai *USB Serial Device (COMx)*). File berikut hanya diperlukan untuk Windows lama atau saat mengganti/memulihkan firmware.

| File | Isi |
|---|---|
| `windows-driver-cantact.zip` | `cantact.inf` / `.cat`: driver port COM untuk Windows 7/8 |
| `firmware/slcan/canable2-b158aa7.bin` / `.dfu` | Firmware **slcan** (dipakai di repo ini, mendukung CAN FD) |
| `firmware/candlelight/canable2_fw-ba6b1dd.bin` / `.dfu` | Firmware **candleLight / gs_usb** (tanpa CAN FD) |
| `tools/ImpulseRC_Driver_Fixer.exe` | Memperbaiki driver DFU bila mode BOOT tidak dikenali setelah memakai updater online |

Mengganti firmware:

1. Cabut CANable, hubungkan (short) dua pad **BOOT** di bagian bawah board, lalu colokkan USB. Board masuk mode DFU.
2. **Online:** buka https://canable.io/updater/ di Chrome, pilih firmware *CANable 2.0 slcan*, klik Update. Kalau DFU tidak terdeteksi, jalankan `ImpulseRC_Driver_Fixer.exe`.
3. **Offline:** tulis file `.bin` ke alamat `0x08000000` dengan STM32CubeProgrammer (mode USB/DFU), atau file `.dfu` dengan DfuSe.
4. Lepas short BOOT, cabut-colok USB.

STM32CubeProgrammer dan DfuSe (dari STMicroelectronics) tidak disertakan karena ukurannya besar (>200 MB); unduh dari https://www.st.com/en/development-tools/stm32cubeprog.html

## Checksum SHA-256

```
2418b983073c5ab90836bba54e3ad4d10bd9bad7ee1875cb405ba48fbf3fe41e  korlan/usb2can_winusb.msi
789b54b94f35d8cf20d1ce615b37fca1a19711ab0c6c8c20d1931355259fc8fc  korlan/usb2can_canal_v2.0.0.zip
5d55773964655f77b5fc4762837dab0b20d6b6e53b3c31a26d417ed10460909d  canable/windows-driver-cantact.zip
40a913e61d9dfb848e498d72a3053d0512eae565a97686e90ea6d07b83210122  canable/firmware/slcan/canable2-b158aa7.bin
3f077d80f0ffd1c4560de723dab009409893eb3d3beb1732f563f12b48efb8d5  canable/firmware/slcan/canable2-b158aa7.dfu
81e6a6754a79843f6c8620c6a88b5646abf5c9723458e22b573fdab46d934bf8  canable/firmware/candlelight/canable2_fw-ba6b1dd.bin
e42c9590976f2118be1019fb9efdc15279af2f440f3228bc6a2cccdabac9c3ff  canable/firmware/candlelight/canable2_fw-ba6b1dd.dfu
7da7ca91fb0da1edd8e9c5355b48597883bc1bfdecfeab1b9200aeb08d3d2771  canable/tools/ImpulseRC_Driver_Fixer.exe
```

Cek di Windows: `certutil -hashfile <nama file> SHA256`
