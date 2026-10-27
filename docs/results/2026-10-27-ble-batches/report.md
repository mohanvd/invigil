# BLE readings in batches: 2026-10-27

Firmware 0.2.0 changes how BLE readings are sent. In 0.1.1 every advertisement was its own MQTT message. Now the readings from each scan window go out together in `ble` messages of up to 1400 bytes each, about 17 readings per message ([contract](../../contract.md#ble-readings)). Everything else matches the [send-window-500 run](../2026-10-27-send-window-500/report.md): the 500 ms send window, the rule that the unit waits for the drain before it scans again, and the same room.

Ten minutes in the same crowded room (109 devices heard, about 71 BLE readings a second). **The unit scanned 85 % of the time instead of 53 %, BLE latency p95 fell from 4.6 s to 1.0 s, and readings over 2 s fell from 13.4 % to 1.2 %.** Every send window drained before the next scan, and one frame landed in a scan window, at the same 5-minute rhythm as before. Design requirement 4 (2 s) now holds for 98.8 % of readings at this load, not all of them: long send windows still happen in 12 of 60 summaries.

No raw data or addresses are in this report. The session stays in `data/raw/` on the laptop. `summary.txt` has the unit's 60 summary lines, which hold counts only.

## Setup

| Part | Setting |
| --- | --- |
| Unit | N1, firmware 0.2.0. The nRF24L01 still fails its boot self-check (wiring), so this run has BLE and status only, no spectrum, like the 0.1.1 run |
| Network | Router 2.4 GHz fixed on channel 6 |
| Laptop | `python -m invigil start --session batch-10min` |
| Devices nearby | Not controlled, the same crowded room: 109 distinct hashed addresses in 10 minutes (116 in the 0.1.1 run) |
| Window | 600 s, 09:23:52 to 09:33:52, starting about 110 s after the unit booted |

A first attempt at 09:14 stopped after about 350 s, when the unit's USB connection dropped and it rebooted. It is not used here. Its numbers looked the same as this run's.

## Clock

From the session's `clock.json`: the laptop was 167.8 ms behind NTP at the start and 143.5 ms behind at the stop. Latency below is corrected by the mean, -155.7 ms, and is good to about ±100 ms.

## Results

| | This run (0.2.0, batches) | [0.1.1](../2026-10-27-send-window-500/report.md) (one message per reading) |
| --- | --- | --- |
| BLE readings a second | **71.1** published | 66.6 published |
| BLE messages a second | **4.2** (2,499 in 600 s) | about 67 |
| Readings per BLE message | 17.1 on average | 1 |
| `mqtt_busy` (waits for the MQTT output buffer) | **0** | 55,641 in 600 s (59 of 60 summaries) |
| `tx_in_scan` | 1 in 600 s | 3 in 600 s |
| Send windows over the limit | **13 in 600 s** (12 of 60 summaries) | 75 in 600 s (45 of 60 summaries) |
| Longest send window per 10 s | **median 170 ms**, worst 2,739 ms | median 2,138 ms, worst 5,000 ms |
| Scan windows per 10 s | **8.5** on average, 4 to 10 | 5.3 on average, 0 to 9 |
| Time spent scanning | **85 %** | 53 % |
| BLE latency p50 / p95 / p99 / max | 590 / **1,025** / 2,108 / 3,473 ms | 747 / 4,604 ms / not reported / 18,081 ms |
| BLE readings over 2 s | **1.16 %** | 13.4 % |
| Status latency p50 / p95 | 69 / 169 ms | 108 / 5,495 ms |
| `ble_dropped` | 0 | 0 |
| Rejected by the logger | 0 | 0 |

Wi-Fi stayed up and MQTT stayed connected in every summary line. The logger wrote 42,654 rows to `ble.csv`, one per reading, with the same columns as before.

### The long send windows

48 of the 60 summaries had a longest send window under 400 ms. The other 12 had one between 1.3 and 2.7 s, and they do not follow the load: the slowest one (2,590 ms at t=354 s) came in a 10 s stretch with only 316 readings, well under the median of 742. `mqtt_busy` stayed 0, so the unit was never waiting for room in its own buffer. It was waiting for the broker's acknowledgement.

The likely cause is a lost Wi-Fi frame. With only a few messages per send window, TCP has no later segments to trigger a fast resend, so lwIP waits for its retransmission timer, which is around a second or more. This was not confirmed with a packet capture.

### The frame in a scan window

`tx_in_scan` was 1 once, at t=294 s of uptime, in a stretch with no overrun. The 0.1.1 run saw the same at t=291, 303 and 582 s. The rhythm points again to the router or the laptop checking the unit's address (ARP), not to MQTT.

## What this means

- Batching removes the per-message cost that made the send windows long in a crowded room. The unit now sends about 4 messages a second instead of 67, and it is back to scanning most of the time.
- At about 70 BLE readings a second, design requirement 4 (unit to dashboard within 2 s) holds for 98.8 % of readings. The rest come from the occasional slow acknowledgement, not from the amount of data.
- The hall during an exam should be quieter than this room. That needs measuring in the hall, not assuming.

## Next steps

1. **Fix the radio wiring** and repeat this run with spectrum on, to see `sweeps_discarded` and the cost of the spectrum message.
2. **Look at the slow acknowledgements**, for example with a packet capture on the laptop during a run, to confirm whether they are TCP retransmissions. If they are, a shorter lwIP retransmission timeout is the thing to test.
3. **Find the 5-minute sender**, for example with a static ARP entry for the unit on the laptop.
4. Repeat in the hall.
