**English** | [Bahasa Indonesia](README.md)

# Adapter drivers and firmware

Backup copies of the driver and firmware files used in this repository, so they stay available even if the manufacturers move or remove them. Every file is copied unchanged from the manufacturer's official package.

> **Copyright:** the files in this folder belong to their respective makers (8devices, Makerbase / CANable, ImpulseRC) and are **not** covered by this repository's MIT license. If the official version is still available, prefer downloading it from the original source (links below).

## Korlan USB2CAN (8devices) – `korlan/`

| File | Contents |
|---|---|
| `usb2can_winusb.msi` | WinUSB driver for Windows. Run as Administrator; afterwards the Korlan shows up as **USB2CAN** in Device Manager |
| `usb2can_canal_v2.0.0.zip` | USB2CAN CANAL DLL v2.0.0: `x64/Release/usb2can.dll` (64-bit Python) and `x86/Release/usb2can.dll` (32-bit Python) |

Usage: install the driver, then copy `x64/Release/usb2can.dll` from the zip into the program folder (main folder or `dual-adapter/`). Original source: the 8devices Korlan USB2CAN product page, *Resources* section: https://wiki.8devices.com/korlan

## Makerbase CANable V2.0 / V2.0 Pro – `canable/`

On Windows 10/11 with **slcan** firmware the CANable **needs no driver** (it shows up as *USB Serial Device (COMx)*). The files below are only needed on older Windows or when changing/recovering the firmware.

| File | Contents |
|---|---|
| `windows-driver-cantact.zip` | `cantact.inf` / `.cat`: COM-port driver for Windows 7/8 |
| `firmware/slcan/canable2-b158aa7.bin` / `.dfu` | **slcan** firmware (used in this repo, supports CAN FD) |
| `firmware/candlelight/canable2_fw-ba6b1dd.bin` / `.dfu` | **candleLight / gs_usb** firmware (no CAN FD) |
| `tools/ImpulseRC_Driver_Fixer.exe` | Fixes the DFU driver when BOOT mode is not recognised after using the online updater |

Changing the firmware:

1. Unplug the CANable, short the two **BOOT** pads on the underside of the board, then plug in USB. The board enters DFU mode.
2. **Online:** open https://canable.io/updater/ in Chrome, choose *CANable 2.0 slcan*, click Update. If DFU is not detected, run `ImpulseRC_Driver_Fixer.exe`.
3. **Offline:** write the `.bin` file to address `0x08000000` with STM32CubeProgrammer (USB/DFU mode), or the `.dfu` file with DfuSe.
4. Remove the BOOT short and re-plug USB.

STM32CubeProgrammer and DfuSe (from STMicroelectronics) are not included because they are large (>200 MB); download them from https://www.st.com/en/development-tools/stm32cubeprog.html

## SHA-256 checksums

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

Check on Windows: `certutil -hashfile <file name> SHA256`
