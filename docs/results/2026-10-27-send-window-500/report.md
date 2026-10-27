# Send window 500 ms, and no scanning while sending: 2026-10-27

Firmware 0.1.1 changes two things:

- **The send window limit** goes from 300 to 500 ms.
- **A scan window never starts while the unit still has data in flight.** At the end of a send window the unit waits until the MQTT output buffer is empty and the broker has acknowledged every TCP segment. If that takes longer than 500 ms, it keeps waiting and counts an overrun.

Ten minutes in a crowded room (116 devices heard). **The MQTT traffic no longer lands in scan windows. Three frames still did, at a regular 5-minute rhythm that points to network housekeeping, not to MQTT.** The cost under this load is large: send windows often took seconds, the unit scanned only 53% of the time, and **BLE latency rose to p95 4.6 s, which fails design requirement 4 at this load.**

No raw data or addresses are in this report. The session stays in `data/raw/` on the laptop.

## Why

At 08:00 this morning on firmware 0.1.0, with many devices around, the unit had about 127 BLE readings a second to send. Send windows hit their 300 ms limit (`send_overruns` 3 in 10 s), and the rest of the data went out during scan windows (`tx_in_scan` 6 in 10 s). The [MQTT contract](../../contract.md) says the unit must not scan the 2.4 GHz band while it transmits.

## Setup

| Part | Setting |
| --- | --- |
| Unit | N1, firmware 0.1.1. The nRF24L01 failed its boot self-check this morning (wiring, see below), so this run has BLE and status only, no spectrum |
| Network | Router 2.4 GHz fixed on channel 6 |
| Laptop | `python -m invigil start --session send500-10min` |
| Devices nearby | Not controlled, a crowded room: 116 distinct hashed addresses in 10 minutes |
| Window | 600 s, 08:39:30 to 08:49:30, starting about 30 s after the unit booted |

## Clock

From the session's `clock.json`: the laptop was 123.9 ms behind NTP at the start and 136.5 ms behind at the stop. Latency below is corrected by the mean, -130.2 ms, and is good to about ±100 ms.

## Results

| | This run (0.1.1, 500 ms, drain first) | 08:00 today (0.1.0, 300 ms), one 10 s line | [Yesterday](../2026-10-26-latency/report.md) (0.1.0, 300 ms, quieter room) |
| --- | --- | --- | --- |
| BLE readings a second | 66.6 published | about 127 captured | 41.6 |
| `tx_in_scan` | **3 in 600 s** | 6 in 10 s | 2 in 600 s |
| Send windows over the limit | 75 in 600 s (45 of 60 summaries) | 3 in 10 s | 0 |
| Longest send window per 10 s | median 2,138 ms, worst 5,000 ms | 300 ms (cut off) | 118 ms |
| Scan windows per 10 s | 5.3 on average, 0 to 9 | about 8 | 9 to 10 |
| Time spent scanning | 53 % | about 80 % | 95 % |
| BLE latency p50 / p95 / max | 747 ms / **4,604 ms** / 18,081 ms | not measured | 558 ms / 989 ms / 1,108 ms |
| BLE readings over 2 s | **13.4 %** | not measured | 0 % |
| Status latency p50 / p95 | 108 ms / 5,495 ms | not measured | 59 ms / 104 ms |
| `ble_dropped` | 0 | 0 | 0 |
| Rejected by the logger | 0 | 0 | 0 |

Wi-Fi stayed up and MQTT stayed connected in every summary line.

### The three frames in scan windows

| Summary | `tx_in_scan` | `send_overruns` in that 10 s |
| --- | --- | --- |
| t=291 s | 1 | 2 |
| t=303 s | 1 | 1 |
| t=582 s | 1 | 0 |

The one at t=582 s came in a 10 s stretch with no overrun at all, and the times repeat the 291 s spacing seen [yesterday](../2026-10-26-latency/report.md#window-timing). So these are not MQTT data. The likely source is the router or the laptop checking the unit's address (ARP), which lwIP answers at once. The firmware docs list this as the one source the unit cannot hold back. It was not confirmed with a packet capture. When the radio works, a sweep that such a frame touches is thrown away (`sweeps_discarded`), so it never reaches a spectrum message.

### Why the send windows got so long

The unit published about 67 BLE readings a second this morning and could not keep up. Yesterday, in a quieter room, a send window of under 120 ms cleared about 55 readings each cycle. Every BLE reading is its own small MQTT message, and the unit now also waits for the broker's acknowledgements before it scans again. In a crowded room the 2.4 GHz channel is busy, so each round trip takes longer. The Wi-Fi airtime was not measured, so this is the likely explanation, not a confirmed one. The longer the send window, the less the unit scans, and the longer readings wait in the buffer, which is where the 4.6 s p95 comes from.

## What this means

- The rule "never scan while sending" now holds for everything the unit sends on its own. What is left is a few frames every 5 minutes from network housekeeping.
- At this load, the rule costs latency and scan time. Design requirement 4 (2 s) is not met at about 120 BLE advertisements a second.
- In the hall during an exam, phones should be off or in bags, so the load is likely lower than this room. That needs measuring in the hall, not assuming.

## Next steps

1. **Fix the radio wiring** and repeat this run with spectrum on, to see `sweeps_discarded`.
2. **Send fewer, bigger packets.** With the unit now waiting for every acknowledgement before it scans, Nagle's algorithm can be turned back on during send windows, so many small messages share one TCP segment. This needs no contract change. Measure it the same way.
3. **Send less BLE data.** For example one message per device per scan window with its strongest RSSI and a count, instead of one per advertisement. This changes the [MQTT contract](../../contract.md) and the features, so it needs a decision first.
4. **Find the 5-minute sender**, for example by adding a static ARP entry for the unit on the laptop and checking whether the rhythm stops.
5. Repeat in the hall.
