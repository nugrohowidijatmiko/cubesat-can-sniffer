**English** | [Bahasa Indonesia](README.md)

# Makerbase CANable V2.0 Pro version (slcan)

This folder contains a version of the sniffer that uses a **Makerbase CANable V2.0 Pro** instead of the Korlan USB2CAN. The CFP/CSP logic, the GUI and the simulation mode are the same as the Korlan version in the main folder; only the way the program connects to the adapter is different.

Tutorial (in Indonesian): *Sniffing CAN Bus CubeSat (libcsp) dengan Makerbase CANable V2.0 Pro dan GUI Python* on [nugrohowidijatmiko.blogspot.com](https://nugrohowidijatmiko.blogspot.com/).

> The GUI labels, code comments and program messages are in Indonesian, as in the main folder.

## Folder contents

| File | Purpose |
|---|---|
| `csp_can_tool.py` | CFP/CSP library + command-line tool (`list`, `monitor`, `ping`, `hk`, `payload`, `echo`), default interface `slcan` |
| `csp_can_gui.py` | Tkinter GUI: choose *Adapter* `slcan` and the CANable COM *Port*, or `simulasi` (simulation) without hardware |
| `test_canable.py` | Quick connection test: list COM ports, then print CAN frames for 5 seconds |

## Differences from the Korlan version

| | Korlan USB2CAN | Makerbase CANable V2.0 Pro |
|---|---|---|
| Connector | DB9 | Screw terminal CANH / CANL / GND |
| Isolation | No | Yes (galvanic) |
| 120 Ω terminator | None | On board, switchable |
| Windows driver | WinUSB + `usb2can.dll` | None needed (slcan firmware = COM port) |
| python-can | `interface="usb2can"` | `interface="slcan"` |
| Bus error type reporting | Yes (stuff, ACK, CRC, etc.) | Not in slcan firmware |

## Quick start

1. **Check the firmware.** Plug in the CANable and open Device Manager. **slcan** firmware shows up as a COM port (e.g. COM7). If it shows up as a "candleLight" device instead, flash *CANable 2.0 slcan* from [canable.io/updater](https://canable.io/updater/) (Chrome, board in boot/DFU mode).
2. **Python libraries.**
   ```bash
   pip install python-can pyserial
   ```
3. **Connect the CANable to the bus** in parallel, in the middle of the bus: CANH–CANH, CANL–CANL, GND–board GND. **Switch off the CANable's 120 Ω terminator**, because the bus is terminated only at both ends (the OBC and EPS modules). With all boards off, CANH–CANL should measure about 60 Ω; about 40 Ω means the CANable terminator is still on.
4. **Connection test** (replace `COM7` with your port):
   ```bash
   python test_canable.py
   ```
5. **Run the GUI.**
   ```bash
   python csp_can_gui.py
   ```
   Choose *Adapter* `slcan`, make sure *Port* shows the CANable COM port (the **Cari** (search) button rescans; a port with VID `16D0` is selected automatically), then click **Hubungkan** (connect).

### Without the GUI

```bash
python csp_can_tool.py list
python csp_can_tool.py --channel COM7 monitor --frames
python csp_can_tool.py --channel COM7 ping 2
python csp_can_tool.py hk
python csp_can_tool.py payload on
python csp_can_tool.py echo 1 "Halo OBC"
```

Without `--channel`, the CANable port is found automatically. Other options: `--interface` (default `slcan`, or `virtual`), `--bitrate` (default 1000000), `--timeout`.

## Troubleshooting

slcan firmware does not report the type of bus error. The **Kondisi bus** (bus condition) line in the GUI shows **OK** when frames arrived in the last 3 seconds, or **DIAM: tidak ada frame** (silent: no frames) when the bus is quiet.

| Symptom | Likely cause | Fix |
|---|---|---|
| No new COM port | candleLight firmware, charge-only USB cable | Flash slcan firmware, use a data USB cable |
| "could not open port" / "Access is denied" | COM port is used by another program | Close the other program, re-plug the CANable |
| Bus condition "DIAM", 0 CAN frames | CANH/CANL swapped or not connected, different bitrate, no common GND | Check wiring and GND, use 1 Mbit/s on both sides |
| Lost frames / CFP reassembly errors | CANable terminator still on (±40 Ω) or no termination | Switch off the CANable terminator, fit 2×120 Ω at the bus ends |
| Errors even with correct wiring | MCP2551 powered at 5 V needs TXD ≥ 3.5 V, STM32 gives only 3.3 V | Use an SN65HVD230, or a 2.2 kΩ pull-up from CTX to 5 V + PA12 open-drain |

In normal mode the CANable also ACKs frames, so a single board together with the CANable is still readable.
