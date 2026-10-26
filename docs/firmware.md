# Unit firmware

The firmware for sensor unit N1: a Raspberry Pi Pico 2 W (RP2350 + CYW43439) with an nRF24L01+PA+LNA on SPI0.

**Status: version 0.1.0 runs on the real unit N1.** On the first hardware run (2026-10-26) every self-check passed, the unit published BLE, spectrum and status messages, and the logger rejected none of them ([first boot report](results/2026-10-26-first-boot/report.md)). The BTstack byte order is checked and correct ([byte-order report](results/2026-10-26-byte-order/report.md)). The timing values are still starting guesses, and the [To measure](#to-measure) section lists what is left to check on the board.

- Toolchain: the official Pico SDK **2.3.1** in C with CMake, Arm GNU Toolchain **15.2.Rel1**, picotool **2.3.1**, built with the Raspberry Pi Pico VS Code extension. No Arduino, no Arduino-Pico core, no PlatformIO, no ESP code.
- Board: `pico2_w`.
- The versions are pinned in the extension block of `firmware/CMakeLists.txt`. CI reads them from there.

Wiring is in the [README](../README.md#wiring). The message formats are in the [MQTT contract](contract.md).

## What it does

The unit repeats one cycle, as the [MQTT contract](contract.md) requires:

1. **Scan window** (1000 ms). BLE scan on, nRF24L01 sweeps channels 0 to 125 back to back. No MQTT traffic.
2. **Send window** (up to 300 ms). BLE scan off, sweeps stopped. Publish one spectrum message for the window (`ts` is the end of the scan window), then the buffered BLE readings, oldest first, then a status message if one is due (every 10 s). The window ends when the buffer is empty, or when time runs out. Leftovers wait for the next send window. Then the unit waits until everything has left lwIP for the radio.
3. **Quiet gap** (50 ms), then the next scan window.

The cycle only runs while Wi-Fi is up, the clock is set by SNTP and MQTT is connected. Nothing is published before the clock is set, because the contract rejects unsynced timestamps. Reconnecting happens between cycles, never inside a scan window.

## Modules

| File | Job |
| --- | --- |
| `src/config.h` | Pins, timing constants (each marked as a guess to measure), the debug flag. Includes `secrets.h` |
| `src/wifi_sta.c` | Wi-Fi station (WPA2 personal, country Egypt), reconnect with backoff (1 s doubling to 30 s), SNTP clock, prints the Wi-Fi channel and RSSI |
| `src/mqtt_link.c` | lwIP MQTT, QoS 0, client ID `invigil-N1`, reconnect with backoff, waits when the output buffer is full |
| `src/ble_scan.c` | BTstack observer, passive scan, duplicate filtering off, boot self-check with the hash test vector, buffer of 1024 readings |
| `src/nrf_scan.c` | nRF24L01 on SPI0 at 4 MHz, receive only, RPD hits per channel per window, sweep timing |
| `src/main.c` | The cycle, watchdog (8 s), LED, 10 s summary on USB serial |
| `src/lwipopts.h`, `src/btstack_config.h` | lwIP and BTstack settings |
| `portable/` | Code that needs no Pico SDK, tested on a PC: SHA-256 and address hashing, manufacturer ID parsing, JSON payloads, spectrum counting, the reading buffer, and the receive-only nRF24L01+ driver |
| `tests/` | Host tests for `portable/`, and `check_contract.py`, which runs sample payloads through `server/contract.py` |

### Privacy and receive-only rules in the code

- The BTstack callback hashes each address at once (`sha256(salt + 6 address bytes)`, first 12 hex chars, see [hashing](hashing.md)). Only the hash enters the buffer. The payload builder refuses any `addr` that is not 12 lowercase hex characters, so a raw address cannot be published by mistake.
- No advertising payload is kept. Only the manufacturer company ID is read from it.
- The nRF24L01 driver has no code for any transmit command. Every register write goes through an allow-list that refuses a value that would leave RX mode, turn auto-ack on, or start the carrier test mode. The host tests run the driver against a fake radio that fails on any other command.
- The unit refuses to publish BLE readings while `HASH_SALT` is empty or is the test-vector salt.

## Build on Windows

You need a Windows PC with internet access the first time. The Pico VS Code extension downloads the SDK, the compiler, CMake, Ninja and picotool into `%USERPROFILE%\.pico-sdk`. These steps were run on this project on 2026-10-26 with extension 0.23.0.

1. Install [Visual Studio Code](https://code.visualstudio.com/) and [Git](https://git-scm.com/).
2. In VS Code, open Extensions, search for **Raspberry Pi Pico**, and install the one published by Raspberry Pi.
3. Clone the repo, then create your secrets file (next section).
4. In VS Code, use **File > Open Folder** and open the `firmware` folder of the repo, not the repo root. The extension looks for `CMakeLists.txt` in the folder you open.
5. The extension reads the pinned versions from `firmware/CMakeLists.txt` (SDK 2.3.1, toolchain 15_2_Rel1, picotool 2.3.1) and offers to download them. Accept. If nothing happens, press Ctrl+Shift+P and run **Raspberry Pi Pico: Import Pico Project**. Pick the `firmware` folder and SDK 2.3.1, check under Show Advanced Options that the toolchain is 15.2.Rel1, leave Ninja and CMake on their defaults and **Enable CMake-Tools extension integration** unchecked, then click Import. The download goes to `%USERPROFILE%\.pico-sdk`.
6. Click **Compile** in the status bar at the bottom, or press Ctrl+Shift+P and run **Raspberry Pi Pico: Compile Project**.
7. The output is `firmware\build\invigil.uf2`. The build folder is gitignored.

If the build stops with `firmware/secrets.h is missing`, do the next section first.

The import creates `firmware/.vscode/` and `firmware/.gitignore`, and rewrites the line endings of `firmware/CMakeLists.txt` and `firmware/pico_sdk_import.cmake` without changing their content. None of these are for committing. Restore the two files with `git restore firmware/CMakeLists.txt firmware/pico_sdk_import.cmake`, and add `firmware/.vscode/` to `.git/info/exclude`.

### Secrets

The Wi-Fi password, MQTT login and hash salt live in `firmware/secrets.h`, which is gitignored. Only the template is committed.

```powershell
Copy-Item firmware\secrets.h.example firmware\secrets.h
```

Then fill it in:

| Field | Value |
| --- | --- |
| `WIFI_SSID`, `WIFI_PASSWORD` | The hall Wi-Fi. WPA2 personal only |
| `MQTT_HOST` | The laptop's IPv4 address (run `ipconfig` on the laptop). Not a host name |
| `MQTT_PORT` | `1883` |
| `MQTT_USER`, `MQTT_PASSWORD` | The same login as `server/config.toml` and `server/mosquitto.passwd` |
| `HASH_SALT` | The same value as `hash_salt` in `server/config.toml`. The unit will not publish BLE readings while it is empty |
| `NODE_ID` | `"N1"` |
| `SNTP_SERVER` | `"pool.ntp.org"`, or the laptop's IP address if the hall network has no internet. Then run an NTP server on the laptop |

The `.uf2` that CI uploads is built from the template, with placeholder secrets and an empty salt. It only proves the code builds. Flash a build made with your own `secrets.h`.

### Host tests

The code in `firmware/portable/` is tested on a PC with its normal C compiler, no Pico SDK. CI runs this on every pull request. To run it yourself you need CMake and a C compiler (gcc or clang; on Windows, for example from MSYS2), then from the repo root:

```bash
cmake -S firmware/tests -B firmware/build/tests
cmake --build firmware/build/tests
ctest --test-dir firmware/build/tests --output-on-failure
python firmware/tests/check_contract.py firmware/build/tests/samples.tsv
```

## Flash

1. Unplug the Pico 2 W.
2. Hold the **BOOTSEL** button and plug the USB cable into the laptop. Release the button. A drive named `RP2350` appears.
3. Drag `firmware\build\invigil.uf2` onto that drive. The drive disappears and the unit reboots into the new firmware.

When the unit is already running this firmware, picotool can flash it without the BOOTSEL button. It reboots the unit into BOOTSEL over USB, loads the file, and starts it:

```powershell
& "$env:USERPROFILE\.pico-sdk\picotool\2.3.1\picotool\picotool.exe" load -f -x firmware\build\invigil.uf2
```

To watch the log, open the unit's USB serial port: the Serial Monitor tab in VS Code, or PuTTY on the COM port Windows assigns. The unit waits up to 3 s at boot for a terminal, so the self-checks are not missed. If you connect later, unplug and replug. The terminal must set DTR, which those tools do: the firmware only treats the port as open when DTR is set.

## First boot

This is what unit N1 printed on its first boot (2026-10-26), with the network name and addresses replaced by examples. Your numbers will differ.

```
Invigil unit N1, firmware 0.1.0, Pico SDK 2.3.1
last reset: not a watchdog timeout
self-checks:
  PASS  node ID "N1"
  PASS  hash test vector: got 41239c0be85e, expected 41239c0be85e
  PASS  hash salt: set
  PASS  nRF24L01: answers on SPI0 at 4000 kHz, RX mode, auto-ack off
timing: scan 1000 ms, send up to 300 ms, quiet gap 50 ms, status every 10000 ms
wifi: connecting to "hall-wifi"
wifi: connection failed
wifi: retrying in 1 s
wifi: connecting to "hall-wifi"
wifi: connected to "hall-wifi", IP 192.168.1.23
wifi: channel 6 (2437 MHz, nRF channels 27-47), RSSI -40 dBm
sntp: asking pool.ntp.org for the time
sntp: clock set to 2026-10-26 16:17:21 UTC
mqtt: connecting to 192.168.1.10:1883 as invigil-N1
mqtt: connected
sntp: clock corrected by +134 ms
summary t=21s windows=9 sweeps_per_window=42 sweep_us=23354 sweep_us_max=24785 ble_captured=465 ...
```

What to look for:

- `last reset: WATCHDOG TIMEOUT` means the unit froze for 8 s and the watchdog restarted it. Note what it was doing.
- Each self-check says PASS or FAIL. A failed check does not stop the unit, but it changes what is sent:
  - **hash test vector FAIL**: BLE stays off and no BLE reading is ever published. If it also says the bytes are reversed, see the byte-order check below.
  - **hash salt FAIL**: set `HASH_SALT` in `secrets.h`. BLE stays off until then.
  - **nRF24L01 FAIL**: check the wiring and power. BLE keeps running, but no spectrum messages are sent.
- `wifi: network not found` over and over: the unit cannot see the network. The Pico 2 W only uses 2.4 GHz, and on the first run it never found a network on channel 13, even though the firmware sets the country to Egypt, which allows channels 1 to 13. Set the router's 2.4 GHz channel to a fixed 1, 6 or 11, not Auto, and check that 2.4 GHz is on for that network name.
- A single `wifi: connection failed` before connecting is normal. It happened on most boots and the second attempt worked.
- The `sntp: clock corrected` line comes from a second time request. The first answer cannot be corrected for network delay because the clock starts at 1970, so the unit asks again at once.

### LED

| Pattern | Meaning |
| --- | --- |
| Slow blink (1 per second) | Connecting to Wi-Fi |
| Fast blink (5 per second) | Waiting for the clock or the broker |
| Solid | Running: scanning and publishing |
| 3 short blinks, then a pause, repeating | A self-check failed. The serial log says which |

### Summary line

Every 10 s the unit prints one line of `key=value` pairs. These are the numbers for calibration. Counts are for the last 10 s.

| Key | Meaning |
| --- | --- |
| `windows` | Scan windows run |
| `sweeps_per_window` | Average complete sweeps per spectrum message |
| `sweep_us`, `sweep_us_max` | Average and longest time for one 126-channel sweep, in microseconds |
| `ble_captured` | Advertisements added to the buffer |
| `ble_published` | BLE readings handed to MQTT |
| `ble_dropped` | Oldest readings dropped because the 1024-reading buffer was full |
| `ble_buffered` | Readings still waiting |
| `spectrum_sent`, `spectrum_dropped` | Spectrum messages sent, and lost because the send window ran out |
| `status_sent` | Status messages sent |
| `send_ms_max` | Longest send window, in ms |
| `mqtt_busy` | Times the MQTT output buffer was full and the unit waited for it to drain |
| `send_overruns` | Send windows that hit 300 ms before everything left lwIP |
| `tx_in_scan` | Frames lwIP handed to the radio during scan windows. Should be 0 |
| `sweeps_discarded` | Sweeps thrown away because lwIP sent a frame during them |
| `wifi`, `mqtt` | Connection state |

`ble_no_rssi`, `ble_invalid` and `SELF-CHECK FAILED` only appear when they apply.

## What can transmit during a scan window

The contract says the unit must not scan the 2.4 GHz band while it transmits over Wi-Fi. This is what the code does about each source of transmissions, from reading the lwIP 2.2, cyw43-driver and BTstack sources pinned by Pico SDK 2.3.1. None of it has been measured yet.

| Source | What happens | Can it land in a scan window? |
| --- | --- | --- |
| Publishes | Only in send windows. The send window then waits until the MQTT output buffer is empty and TCP has nothing unsent. Nagle is off, so no segment waits for the broker's delayed ack | No, unless a send window hits 300 ms first (`send_overruns`) |
| MQTT keep alive | lwIP's MQTT timer only adds a PINGREQ to the output buffer after 60 s with nothing acknowledged. It does not send it; the next publish does. Every send window publishes | No |
| TCP retransmission | If an ack from the broker is lost, lwIP resends after its timeout, which is at least about a second | Rarely |
| TCP acks | The unit only acks data it receives. At QoS 0 the broker sends nothing back except TCP acks | No |
| ARP | lwIP answers another host's ARP request as soon as it arrives. Its own ARP refreshes only happen when it sends | Yes, when the laptop or router asks |
| DHCP | Lease renewal at half the lease time (12 h for a 24 h lease) | Rarely |
| SNTP | One request an hour, plus a DNS lookup, whenever the lwIP timer fires | Rarely |
| Wi-Fi chip firmware | 802.11 acks for frames it receives, and power-save frames if power saving is on. lwIP does not see these. Power saving is off (`WIFI_PM_MODE` is `CYW43_NONE_PM`) because the default mode sends a power-save frame about 200 ms after the last packet, which would fall inside every scan window | 802.11 acks only, when something arrives |
| Reconnecting | Wi-Fi and MQTT reconnects only start between cycles, and the cycle stops while either is down | No |
| Bluetooth | Passive scan, so the Bluetooth side never transmits | No |
| nRF24L01 | Receive only, auto-ack off | No |

Two counters in the summary check the lwIP part on the real unit. `tx_in_scan` counts frames lwIP hands to the radio during scan windows. `sweeps_discarded` counts sweeps thrown away because such a frame went out while they ran, so they never reach a spectrum message. Frames the Wi-Fi chip sends on its own are not counted. Measure those with the spectrum itself (see below).

## To measure

These depend on hardware behavior, so they are tests to run, not numbers to assume. Save each run's summary lines, plots and a short note in `docs/results/YYYY-MM-DD-<name>/`.

**Byte order of BTstack addresses.** Done on 2026-10-26: the order is correct and `hash_bd_addr()` needs no change ([report](results/2026-10-26-byte-order/report.md)). The steps below are kept in case the BTstack version changes. The boot self-check proves the hash code matches [the test vector](hashing.md#test-vector), but it uses BTstack's own text parser. It cannot show the order of the bytes BTstack hands over from a real advertisement. One-time check:

1. In `firmware/src/config.h`, change `#define INVIGIL_DEBUG_RAW_ADDR 0` to `1`, then build and flash. The boot log shows a WARNING that this is a debug build.
2. Install the **nRF Connect** app on a phone and start a scan near the unit. Pick a device whose address does not change, for example a smartwatch or a BLE beacon.
3. The unit prints lines like `debug: raw AA:BB:CC:DD:EE:FF -> hash 0123456789ab`. Compare the raw address with the one nRF Connect shows for the same device.
   - Same order: the hashes are right. Nothing to change.
   - Reversed (the unit shows `FF:EE:DD:CC:BB:AA`): the bytes must be flipped before hashing in `hash_bd_addr()` in `src/ble_scan.c`.
4. Set the flag back to `0`, build and flash again. CI fails if `1` is committed. Do not save the debug log: it holds raw addresses.

**Sweep time.** First result (2026-10-26, 4 MHz SPI over breadboard wires, with the radio on the adapter board): 23.4 ms per 126-channel sweep on average, 25.0 ms at most, 42 sweeps per scan window. Run the unit for 2 minutes with no test devices nearby. Record `sweep_us`, `sweep_us_max` and `sweeps_per_window`. Then raise `NRF_SPI_HZ` (it is 4 MHz because of breadboard jumper wires) and check the sweep time and the nRF self-check still pass.

**Scan window, send window and quiet gap.** With 3 to 5 BLE devices nearby, run for 10 minutes and record `send_ms_max`, `mqtt_busy`, `send_overruns`, `ble_dropped` and `spectrum_dropped`. They should all stay at 0 except `send_ms_max`. If `send_overruns` or `ble_dropped` is not 0, lengthen `SEND_WINDOW_MAX_MS` or `SEND_DRAIN_MS`. Then check the cycle against design requirement 1 (at most 5 s from when a device starts transmitting) and the open question on window length in the [contract](contract.md).

**Does the unit's own Wi-Fi show up in the spectrum.** The unit prints its Wi-Fi channel at connect (for example `nRF channels 27-47`). The router transmits on that channel too, so compare two runs that differ only in the quiet gap. With no test devices, record 5 minutes with `QUIET_GAP_MS` at 50, then 5 minutes at 250. If the hits on the unit's Wi-Fi channels drop with the longer gap, the unit's own frames were reaching scan windows: keep the longer gap. Also check `tx_in_scan` stays at 0 in both runs.

**Wi-Fi power saving.** Run 10 minutes with `WIFI_PM_MODE` set to `CYW43_NONE_PM`, then 10 minutes with `CYW43_PERFORMANCE_PM`, same devices, same positions. Compare `ble_captured`, the hits on the unit's Wi-Fi channel, and the battery current if you have a USB power meter.

**BLE scan interval and window.** With one phone 1 m away advertising at a known rate (for example nRF Connect's advertiser at 100 ms), count `ble_captured` per minute. Try `BLE_SCAN_INTERVAL` and `BLE_SCAN_WINDOW` at 48 and 48, then 96 and 96, and keep the one that catches more.

**Wi-Fi channel reading.** Check that the channel the unit prints matches the router's settings page. The firmware reads it with a raw driver request whose answer format is assumed. First check (2026-10-26): with the router's 2.4 GHz channel fixed on 6, the unit printed channel 6 and the laptop saw the access point on channel 6.

**RPD threshold and module.** The datasheet puts the RPD threshold at about -64 dBm at the chip. The PA+LNA module adds gain in front of it, and many modules carry a clone chip. Put a phone streaming audio over Bluetooth 0.5 m, 1 m, 2 m and 3.5 m from the unit and record the hit counts. With no devices, hits outside the Wi-Fi block should be near 0.

**Clock offset.** Compare the unit's `ts` with the logger's `rx_ts` on the laptop. Check both clocks against the same NTP server before any latency result (design requirement 4).

## Updating the pinned versions

To move to a newer Pico SDK, change `sdkVersion`, `toolchainVersion` and `picotoolVersion` together in `firmware/CMakeLists.txt`. Use the combination the Pico VS Code extension lists for that SDK. If the toolchain changes, add its SHA-256 (from the `.sha256asc` file Arm publishes next to the download) to the firmware job in `.github/workflows/ci.yml`. Update the versions in this page too.
