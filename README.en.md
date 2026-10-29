**English** | [Bahasa Indonesia](README.md)

# CubeSat CAN Sniffer (libcsp) – Korlan USB2CAN + Python GUI

Companion code for the tutorial **"Sniffing a CubeSat CAN Bus (libcsp) with Korlan USB2CAN and a Python GUI"** (written in Indonesian): https://nugrohowidijatmiko.blogspot.com/2026/10/sniffing-can-bus-cubesat-libcsp-dengan.html

A Korlan USB2CAN adapter (8devices) acts as a third "ear" on the CAN bus between two STM32H743 boards (OBC and EPS) that talk using the CubeSat Space Protocol (libcsp 1.6). The Python program shows raw CAN frames, reassembles them into CSP packets, displays EPS housekeeping data, and can send commands (ping, payload ON/OFF, text messages) straight from the laptop.

![CSP Packets tab connected to a real Korlan](docs/gui-paket-csp.jpg)

*The **Paket CSP** (CSP packets) tab with a real Korlan: blue = OBC, red = EPS. The left panel shows EPS housekeeping and the EPS ping result.*

> The GUI labels, code comments and program messages are in Indonesian. This README gives the English meaning of the main labels.

## Repository contents

| File | Purpose |
|---|---|
| `csp_can_tool.py` | CFP/CSP library + command-line tool: `list`, `monitor`, `ping`, `hk`, `payload`, `echo` |
| `csp_can_gui.py` | Tkinter GUI: CSP packet table, CAN frame table, EPS housekeeping panel, command buttons, bus statistics, CSV log export, plus a simulation mode that needs no hardware |
| `test_korlan.py` | Quick connection test: finds the Korlan and prints frames for 5 seconds |
| `docs/` | Diagrams and screenshots from the tutorial |

## Hardware

| Item | Notes |
|---|---|
| Korlan USB2CAN (8devices) | USB-to-CAN adapter, DB9 connector |
| 2 × STM32H743 boards (DevEBox) + MCP2551 modules | OBC and EPS from the previous tutorial |
| 2 × 120 Ω resistors | Terminators at both ends of the bus |
| Female DB9 connector / screw-terminal adapter | To wire the bus to the Korlan |
| Windows laptop + Python 3 (64-bit) | python-can, pywin32, Tkinter |

![Korlan USB2CAN and DB9 pinout](docs/korlan-db9.png)

## Quick start

1. **Driver and DLL.** From the 8devices Korlan USB2CAN product page (*Resources* section), install `usb2can_winusb.msi`, then copy `x64/Release/usb2can.dll` from *USB2CAN CANAL DLL v2.0.0* into this repository folder. Use the x64 DLL with 64-bit Python.
2. **Python libraries.**
   ```bash
   pip install python-can pywin32
   ```
3. **Connect the Korlan to the bus** as a branch in the middle of the bus: DB9 pin 7 = CANH, pin 2 = CANL, pin 3 = GND. Put the 120 Ω terminators at both ends (not on the Korlan). With all boards powered off, CANH–CANL should measure about 60 Ω.

   ![Wiring the Korlan to the OBC–EPS CAN bus](docs/wiring-bus.png)
4. **Test the connection** (replace the serial number with yours):
   ```bash
   python test_korlan.py
   ```
5. **Run the GUI.**
   ```bash
   python csp_can_gui.py
   ```
   Choose *Adapter* `usb2can` (or `simulasi` = simulation, to try it without hardware) and click **Hubungkan** (Connect). The Korlan serial number is detected automatically; **Cari** (Search) scans again.

### Without the GUI

```bash
python csp_can_tool.py list
python csp_can_tool.py monitor --frames
python csp_can_tool.py ping 2
python csp_can_tool.py hk
python csp_can_tool.py payload on
python csp_can_tool.py echo 1 "Halo OBC"
```

Common options: `--interface` (default `usb2can`, or `virtual`), `--channel` (Korlan serial number), `--bitrate` (default 1000000), `--timeout`.

## How it works

libcsp sends CSP packets over CAN using **CFP (CAN Fragmentation Protocol)**. Addressing lives in the 29-bit extended ID: `[SRC 5][DST 5][TYPE 1][REMAIN 8][ID 10]`. Example ID `0x0110645D`: from OBC (1) to EPS (2), BEGIN frame, 25 frames still to come, packet number 93.

![Reading the CAN ID as a CFP header](docs/cfp-decode.png)

`CfpReassembler` mirrors `csp_can_rx()` in libcsp: frames are grouped by (SRC, DST, ID), a BEGIN frame opens a buffer, MORE frames are appended while REMAIN counts down in order, and the packet is complete once the byte count matches the length in the header.

A receiver thread calls `bus.recv()` continuously and puts the results in a queue. The GUI drains the queue every 40 ms (at most 500 items at a time), so the window stays responsive even on a busy bus.

![Sniffer software architecture](docs/arsitektur.png)

The constants in `csp_can_tool.py` (addresses OBC = 1, EPS = 2, PC = 10; ports PING 1, ECHO 10, TLM 11, EPS_HK 12, EPS_CMD 13; the `eps_hk_t` layout) must match the firmware (`cubesat_proto.h`).

## The GUI

Main labels: **Status node** (node status), **EPS housekeeping** (Suhu chip = chip temperature, VDDA, Payload, Uptime), **Perintah** (commands: Ping OBC/EPS, Payload ON/OFF, Kirim = send message), **Statistik bus** (bus statistics; Kondisi bus = bus condition), tabs **Paket CSP** (CSP packets), **Frame CAN** (CAN frames) and **Log**.

**Frame CAN tab**: every frame with its decoded ID (Src, Dst, BEGIN/MORE, Remain, CFP id). A 200-byte telemetry packet = 26 frames (BEGIN remain=25, then MORE 24…0).

![CAN Frames tab](docs/gui-frame-can.jpg)

**Results with real hardware** (Korlan, 1 Mbit/s): both nodes active, bus condition OK, 0 error frames. A Payload ON command from the laptop is answered by the EPS in about 10 ms.

![OBC and EPS read through the Korlan, Payload ON command](docs/gui-payload-on.jpg)

![EPS housekeeping: chip temperature and VDDA](docs/gui-housekeeping.jpg)

**EPS serial log** (USART1, 115200 baud), confirming that what the Korlan sees is really received by the EPS:

![EPS serial log in STM32CubeIDE](docs/eps-serial-log.jpg)

## Troubleshooting

When the bus signal is bad, the Korlan sends status/error messages (first data byte) instead of data frames. The GUI summarizes them every second in the Log tab and in the **Kondisi bus** row. Example with the bus not yet terminated:

![Stuff errors reported by the Korlan](docs/gui-stuff-error.jpg)

| Symptom | Likely cause | Fix |
|---|---|---|
| 0 CAN frames, no errors | Korlan not connected to the bus / no node transmitting | Check the DB9 wiring (pins 7, 2, 3) and that the boards are powered |
| Many stuff errors, bus warning, error passive | No 120 Ω terminators, CANH/CANL swapped, or bitrate mismatch | Fit 2 × 120 Ω (measure ~60 Ω), check CANH–CANH, match the bitrate |
| Only ACK errors | No other node acknowledging | Power up another node (the Korlan also sends ACKs) |
| Errors persist with correct wiring | MCP2551 on 5 V needs TXD ≥ 3.5 V, the STM32 only drives 3.3 V | Use a 3.3 V transceiver (SN65HVD230) or a 2.2 kΩ pull-up from CTX to 5 V + PA12 open-drain |
| "DLL failed to load" | `usb2can.dll` missing / wrong architecture | Copy the x64 DLL into the program folder and use 64-bit Python |

The Korlan acknowledges frames on the bus, so a single board plus the Korlan is still read correctly. This is a quick way to test the OBC and EPS one at a time.

## Notes

- `usb2can.dll` is not included in this repository; download it from 8devices.
- The GUI's `simulasi` mode creates simulated OBC and EPS nodes on a python-can virtual bus that behave like the firmware.

## License

The code in this repository is released under the [MIT](LICENSE) license.
