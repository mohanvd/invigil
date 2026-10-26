# First boot on hardware: 2026-10-26

The first run of firmware 0.1.0 on the real unit N1. Every self-check passed, the unit published BLE, spectrum and status messages, and the logger saved them with nothing rejected. Latency is not valid yet (see [Latency](#latency)).

No raw data or addresses are in this report. The logger test files stay in `data/raw/`, which is gitignored.

## Setup

| Part | Setting |
| --- | --- |
| Board | Raspberry Pi Pico 2 W |
| Radio | nRF24L01+PA+LNA with antenna, plugged into the adapter board (AMS1117-3.3) |
| Radio power | Adapter VCC on VBUS (physical pin 40), GND on pin 23. Signal pins as in the [README](../../../README.md#wiring). IRQ not connected |
| Firmware | 0.1.0, Pico SDK 2.3.1, Arm GNU Toolchain 15.2.Rel1, built locally with a real `secrets.h`. `NRF_SPI_HZ` 4 MHz, `INVIGIL_DEBUG_RAW_ADDR` 0 |
| Wi-Fi | WPA2-Personal, router 2.4 GHz channel fixed on 6 (not Auto). The unit reported RSSI -40 dBm, nRF channels 27-47 |
| Broker | Mosquitto 2.1.2 on the laptop (Windows 11) with `server/mosquitto.conf`: password login, ports 1883 and 9001 |
| Time | SNTP from `pool.ntp.org` |

## Self-checks

```
last reset: not a watchdog timeout
self-checks:
  PASS  node ID "N1"
  PASS  hash test vector: got 41239c0be85e, expected 41239c0be85e
  PASS  hash salt: set
  PASS  nRF24L01: answers on SPI0 at 4000 kHz, RX mode, auto-ack off
```

The hash test vector matched on the RP2350, so BLE publishing is allowed. This does not settle the BTstack byte order. That check is still open (see [Open items](#open-items)).

Boot sequence: the first Wi-Fi attempt failed and the second connected 1 s later. SNTP set the clock and the second request corrected it by +134 ms. MQTT then connected.

## Summary lines

The first four summary lines after boot. Each covers 10 s.

| t | windows | sweeps per window | sweep_us | sweep_us_max | BLE captured = published | spectrum sent | status sent | send_ms_max | tx_in_scan | sweeps_discarded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 12 s | 2 | 41 | 23356 | 24996 | 103 | 2 | 2 | 18 | 1 | 1 |
| 21 s | 9 | 42 | 23354 | 24785 | 465 | 9 | 1 | 88 | 0 | 0 |
| 31 s | 9 | 42 | 23336 | 24894 | 457 | 9 | 0 | 51 | 0 | 0 |
| 42 s | 10 | 42 | 23367 | 24797 | 534 | 10 | 2 | 92 | 0 | 0 |

In every line: `ble_dropped`, `ble_buffered`, `spectrum_dropped`, `mqtt_busy` and `send_overruns` were 0, `wifi=up`, `mqtt=connected`.

- **Sweep time:** 23.4 ms on average for one 126-channel sweep at 4 MHz SPI, 25.0 ms at most. That gives 42 complete sweeps per 1000 ms scan window.
- **Message rates:** about 46 to 53 BLE readings a second from whatever devices were nearby (not controlled or counted), one spectrum message per scan window, and a status message every 10 s.
- **Send window:** at most 92 ms of the 300 ms allowed. No overruns.
- **tx_in_scan:** 1 in the first 10 s after connecting, then 0. The sweep it hit was discarded (`sweeps_discarded=1`), so no published spectrum contains it. An earlier boot without the radio showed `tx_in_scan=2` in its first summary and 0 after. The likely source is traffic right after connecting, such as the second SNTP request or ARP. Not measured yet.

## Logger test

`python -m server.logger --session first-hardware` ran for 35 s against the live unit.

| File | Rows saved |
| --- | --- |
| `ble.csv` | 1639 |
| `spectrum.csv` | 32 |
| `status.csv` | 4 |

The logger rejected 0 messages, so every payload passed the [MQTT contract](../../contract.md) checks in `server/contract.py`.

### Latency

Latency is **not valid** from this run. The logger reported a median of about -960 ms, which would mean messages arrived before they were sent. The laptop clock was the cause: `w32tm /stripchart /computer:pool.ntp.org` showed it 1.45 s behind (three samples, +1.449 s to +1.470 s). The unit's clock was set by SNTP. Sync the laptop clock and measure again before reporting any latency (design requirement 4).

## Problems and fixes

### The unit could not find the Wi-Fi network

The unit printed `wifi: network not found` and kept retrying, for two different reasons.

1. **Channel 13.** With the router's 2.4 GHz channel on Auto, it chose channel 13. The laptop could join it, but the unit never found it. The firmware sets the Wi-Fi country to Egypt, which allows channels 1 to 13, so why the unit misses channel 13 is not known. With the channel set to 6, the unit connected on its next attempt. The router went back to channel 13 after later settings changes until the channel was fixed on 6 instead of Auto.
2. **No 2.4 GHz network.** After some router changes, the network was only broadcast on 5 GHz. The Pico 2 W only uses 2.4 GHz, so it saw nothing.

**Fix:** turn on 2.4 GHz for the network and fix its channel on 6, not Auto. To check from a Windows laptop, run `netsh wlan show networks mode=bssid` and look for a 2.4 GHz entry on a channel from 1 to 11.

### The radio did not answer, and got hot

At first the radio was wired straight to the Pico without the adapter board. Every boot printed `FAIL  nRF24L01: no answer on SPI0 (register read-back failed)`.

- While rewiring, the module was powered with VCC and GND reversed and got hot. The pin table used for that rewiring was worked out from a picture taken at a different angle, and it had the two header rows swapped. VCC may also have been on VBUS (5 V) at the start. Photos suggest it, but this was not confirmed.
- With the polarity corrected, the module stayed cool but still failed. A temporary debug build read CONFIG, SETUP_AW, RF_CH and STATUS and got `0x00` for every byte, including the STATUS byte that every command returns. The expected reset values are `0x08`, `0x03`, `0x02` and `0x0E`. The debug code was removed afterwards and never committed.
- The same module plugged into the adapter board, with the adapter's VCC on VBUS, passed the self-check at once.

**Fix:** use the adapter board, as listed in the README parts list. Wire it by the labels printed on the adapter, not by a picture. On first power-up, touch the radio and unplug at once if it warms up.

The exact cause of the failure on the bare module was not isolated. Likely causes are an unstable 3.3 V supply from the Pico's 3V3 pin for the PA+LNA module (no 100 uF capacitor was fitted), a wiring fault the rewiring onto the adapter happened to fix, or both. The module survived being powered in reverse.

### Other observations

- On several replugs, the Pico came up in BOOTSEL mode instead of running the firmware. `picotool reboot` started it. It is not known whether BOOTSEL was being pressed by accident.

## Open items

- Sync the laptop clock with NTP, then measure latency again.
- The BTstack byte-order check from [To measure](../../firmware.md#to-measure).
- The rest of [To measure](../../firmware.md#to-measure): window timing with 3 to 5 known devices, the unit's own Wi-Fi in the spectrum, power saving, BLE scan settings and the RPD threshold.
- Find out whether `tx_in_scan` is non-zero only in the first summary after connecting, over a longer run.
- Find out why the unit cannot see a network on channel 13.
