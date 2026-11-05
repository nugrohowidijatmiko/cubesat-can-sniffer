**English** | [Bahasa Indonesia](README.md)

# Dual-adapter version: Korlan USB2CAN + Makerbase CANable

One program for both adapters. The GUI and the command-line tool automatically detect a **Korlan USB2CAN** (8devices) and a **Makerbase CANable V2.0 / V2.0 Pro** (slcan firmware), and you can pick or switch adapters without editing the code. The CFP/CSP logic and simulation mode are the same as in the main folder.

> The GUI labels, code comments and program messages are in Indonesian, as in the main folder.

Related tutorials (in Indonesian):
- Korlan: https://nugrohowidijatmiko.blogspot.com/2026/10/sniffing-can-bus-cubesat-libcsp-dengan.html
- CANable: https://nugrohowidijatmiko.blogspot.com/2026/11/sniffing-can-bus-cubesat-libcsp-dengan.html

## Folder contents

| File | Purpose |
|---|---|
| `csp_can_tool.py` | CFP/CSP library + adapter detection + command-line tool (`list`, `monitor`, `ping`, `hk`, `payload`, `echo`), default interface `auto` |
| `csp_can_gui.py` | Tkinter GUI with an *Adapter* choice of `otomatis` (automatic) / `usb2can` / `slcan` / `simulasi` (simulation) and a *Perangkat* (device) list of detected adapters |

## Setup

```bash
pip install python-can pyserial pywin32
```

- **Korlan:** install the 8devices WinUSB driver and copy `usb2can.dll` (x64) into this folder. `pywin32` is used to read the Korlan serial number.
- **CANable:** slcan firmware (shows up as a COM port), use a data USB-C cable. No driver or DLL needed.

Both adapters can be plugged in at the same time, and both can sit in parallel on the same bus.

## Running

```bash
python csp_can_tool.py list
python csp_can_gui.py
```

Example `list` output with both adapters plugged in:

```
usb2can  04EF18C4   Korlan USB2CAN  S/N 04EF18C4
slcan    COM3       CANable  COM3
slcan    COM6       COM6  (STMicroelectronics STLink Virtual COM Port (COM6))   (bukan adapter yang dikenali)
```

In the GUI:

- **Adapter `otomatis`** (default): the **Cari** (search) button fills the **Perangkat** list with every adapter, e.g. `Korlan USB2CAN  S/N 04EF18C4` and `CANable  COM3`. The first recognised adapter is selected; when both are present, the Korlan comes first.
- **`usb2can` / `slcan`**: the list shows only that type.
- You can also type into the device field: `COM3` is treated as a CANable, `04EF18C4` as a Korlan serial number.
- The status bar names the adapter in use, e.g. *TERHUBUNG 1000 kbit/s · Korlan S/N 04EF18C4* (connected).

The command line picks the adapter automatically, or you can force one:

```bash
python csp_can_tool.py monitor --frames
python csp_can_tool.py --interface usb2can --channel 04EF18C4 ping 2
python csp_can_tool.py --interface slcan --channel COM3 hk
```

## Bus condition and errors

| Adapter | *Kondisi bus* (bus condition) line |
|---|---|
| Korlan | Error type read from the adapter's status code: stuff error, form error, ACK error, CRC error, bus warning, error passive, BUS-OFF |
| CANable | slcan firmware does not report error types, so the condition is inferred from traffic: **OK** or **DIAM: tidak ada frame** (silent: no frames) |

Full troubleshooting steps are in the [main README](../README.en.md) (Korlan) and [canable/README.en.md](../canable/README.en.md) (CANable).
