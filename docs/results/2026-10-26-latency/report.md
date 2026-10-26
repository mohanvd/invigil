# Latency and window timing, 10 minutes: 2026-10-26

The first latency figure with the laptop clock checked against NTP, plus the window-timing counters over the same 10 minutes. **Unit to laptop, every message arrived within 1.11 s, under the 2 s of design requirement 4.** Nothing was dropped, and no send window ran over.

No raw data or addresses are in this report. The session stays in `data/raw/` on the laptop.

## Setup

| Part | Setting |
| --- | --- |
| Unit | N1, firmware 0.1.0 (same code as the [first boot](../2026-10-26-first-boot/report.md), rebuilt with a new MQTT password), radio on the adapter board |
| Network | Router 2.4 GHz fixed on channel 6. Unit RSSI -44 dBm |
| Laptop | `python -m invigil start --session latency-10min`: Mosquitto with `server/mosquitto.conf`, the logger, the dashboard |
| Devices nearby | Not controlled: whatever was in and around the room. 34 distinct hashed addresses were heard |
| Window | 600 s, timed on the laptop, from about 40 s after the unit booted |

Latency here is `rx_ts - ts` from the logger's CSV files: the unit's timestamp against the time the laptop received the message. The dashboard uses the same broker, but its own delay in the browser was not measured.

## Clock

`invigil start` and `invigil stop` wrote the laptop clock's offset from `pool.ntp.org` into the session's `clock.json`:

| When | Laptop minus NTP |
| --- | --- |
| Start | -16.3 ms |
| Stop | -77.0 ms |

Every latency below is corrected by the mean, -46.6 ms. The NTP round trip was about 100 to 220 ms, so each offset is only known to within about ±50 to 100 ms, and the unit's own SNTP clock has an error of the same order. Read the figures below as ±100 ms.

## Latency, unit to laptop

| Message | Count | Per second | p50 | p95 | p99 | Max |
| --- | --- | --- | --- | --- | --- | --- |
| BLE | 24,985 | 41.6 | 558 ms | 989 ms | 1,029 ms | 1,108 ms |
| Spectrum | 570 | 0.95 | 52 ms | 96 ms | 134 ms | 144 ms |
| Status | 60 | 0.10 | 59 ms | 104 ms | 137 ms | 139 ms |

- BLE readings wait in the unit's buffer until the scan window ends, by design, so their latency includes up to one 1,000 ms scan window. A reading heard early in a window waits longest. That is why BLE sits around 0.5 to 1 s while spectrum and status, stamped just before sending, take about 50 to 100 ms.
- No BLE reading took more than 2,000 ms (0.00 %).
- The logger rejected 0 messages.

Against design requirement 4 (alert latency, unit to dashboard, within 2 s): the transport part is met with room to spare. The full requirement also needs the model's processing time and the dashboard's delay, which do not exist yet because detections are not published.

## Window timing

From the unit's 60 summary lines over the same 10 minutes:

| Counter | Total | Worst 10 s |
| --- | --- | --- |
| Scan windows | 571 | 10 |
| BLE captured / published | 25,071 / 25,071 | 483 |
| `ble_dropped` | 0 | 0 |
| `spectrum_dropped` | 0 | 0 |
| `send_overruns` | 0 | 0 |
| `mqtt_busy` | 0 | 0 |
| `tx_in_scan` | 2 | 1 |
| `sweeps_discarded` | 2 | 1 |

- **Send window:** at most 118 ms of the 300 ms allowed.
- **Sweeps:** 23.3 ms on average for one 126-channel sweep, 25.4 ms at most, 41 to 42 complete sweeps per scan window.
- **Connection:** Wi-Fi stayed up and MQTT stayed connected in every line. No self-check failure.
- **`tx_in_scan`:** one frame left the Wi-Fi radio during a scan window at t=291 s and another at t=582 s, 291 s apart. Both sweeps it touched were thrown away (`sweeps_discarded`), so no published spectrum contains them. The regular 5-minute spacing points to periodic network traffic, such as the router's address lookups (ARP), which the firmware docs list as the one source that can land in a scan window. Not confirmed.
- **`mqtt_busy`:** 0 in this run. One earlier run showed 8 in a single summary.

## What this does not cover

- The devices were not controlled. The window-timing test in the [firmware docs](../../firmware.md#to-measure) asks for 3 to 5 known devices nearby, which is still to do. This run had more traffic than that (about 42 BLE readings a second), so the window margins above are probably on the safe side.
- Dashboard delay and model processing time, as above.
- One 10-minute run. Repeat it on another day and in the hall before quoting it in the portfolio.
