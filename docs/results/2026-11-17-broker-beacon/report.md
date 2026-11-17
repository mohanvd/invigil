# Finding the broker by beacon: first run on a phone hotspot

Date: 2026-11-17. Unit N1, firmware 0.3.0. Network: an Android phone hotspot, 2.4 GHz, channel 6. The laptop's address came from the hotspot's DHCP. `MQTT_HOST` in `secrets.h` still held an address from the old network (192.168.8.2), so it could not have been what connected.

## Result

- The unit heard the launcher's beacon and connected to the laptop about 1 s after the clock was set. The hotspot passes broadcasts between its devices, so the beacon is enough here.
- `invigil status` showed the unit online with firmware 0.3.0, about 78 BLE readings a second, and no rejected messages.
- **The nRF24L01 self-check failed on this run** (no answer on SPI0), so no spectrum messages were sent. This is a wiring or power fault on the bench, not part of this change: the radio code is the same as in 0.2.0. The spectrum path on 0.3.0 is still to be checked once the radio answers.
- `tx_in_scan` was 2 in the two summaries that contain a clock request (one at boot, one with `sntp: clock corrected`) and 0 in the others. That matches the SNTP row in [What can transmit during a scan window](../../firmware.md#what-can-transmit-during-a-scan-window). The beacon listener added no transmissions.

Not tested yet: the laptop changing address while the unit runs, and two laptops broadcasting at once. Both are covered by host tests only.

## Serial log

The network name is replaced by an example.

```
Invigil unit N1, firmware 0.3.0, Pico SDK 2.3.1
last reset: not a watchdog timeout
self-checks:
  PASS  node ID "N1"
  PASS  hash test vector: got 41239c0be85e, expected 41239c0be85e
  PASS  hash salt: set
  FAIL  nRF24L01: no answer on SPI0 (register read-back failed). Check wiring and power.
        BLE keeps running, no spectrum messages will be sent
  PASS  broker beacon listener (UDP port 18830)
timing: scan 1000 ms, send up to 500 ms, quiet gap 50 ms, status every 10000 ms
mqtt: the broker is found by its beacon on UDP port 18830, fallback 192.168.8.2:1883
wifi: connecting to "phone-hotspot"
wifi: connected to "phone-hotspot", IP 10.139.204.195
wifi: channel 6 (2437 MHz, nRF channels 27-47), RSSI -62 dBm
sntp: asking pool.ntp.org for the time
sntp: clock set to 2026-11-17 07:17:10 UTC
mqtt: connecting to 10.139.204.170:1883 (beacon) as invigil-N1
mqtt: connected
summary t=13s windows=5 sweeps_per_window=0 sweep_us=0 sweep_us_max=0 ble_captured=498 ble_published=498 ble_msgs=29 ble_dropped=0 ble_buffered=0 spectrum_sent=0 spectrum_dropped=0 status_sent=2 send_ms_max=85 mqtt_busy=0 send_overruns=0 tx_in_scan=2 sweeps_discarded=0 wifi=up mqtt=connected SELF-CHECK FAILED: nrf
summary t=23s windows=9 sweeps_per_window=0 sweep_us=0 sweep_us_max=0 ble_captured=853 ble_published=853 ble_msgs=50 ble_dropped=0 ble_buffered=0 spectrum_sent=0 spectrum_dropped=0 status_sent=1 send_ms_max=64 mqtt_busy=0 send_overruns=0 tx_in_scan=0 sweeps_discarded=0 wifi=up mqtt=connected SELF-CHECK FAILED: nrf
summary t=33s windows=9 sweeps_per_window=0 sweep_us=0 sweep_us_max=0 ble_captured=888 ble_published=888 ble_msgs=51 ble_dropped=0 ble_buffered=0 spectrum_sent=0 spectrum_dropped=0 status_sent=0 send_ms_max=107 mqtt_busy=0 send_overruns=0 tx_in_scan=0 sweeps_discarded=0 wifi=up mqtt=connected SELF-CHECK FAILED: nrf
sntp: clock corrected by +140 ms
summary t=44s windows=10 sweeps_per_window=0 sweep_us=0 sweep_us_max=0 ble_captured=906 ble_published=906 ble_msgs=51 ble_dropped=0 ble_buffered=0 spectrum_sent=0 spectrum_dropped=0 status_sent=2 send_ms_max=68 mqtt_busy=0 send_overruns=0 tx_in_scan=2 sweeps_discarded=0 wifi=up mqtt=connected SELF-CHECK FAILED: nrf
```

## Status screen

```
Broker       running at localhost:1883 (started by the launcher, PID 46048)
Beacon       broadcasting on UDP port 18830 (PID 42988)
Logger       data\raw\2026-11-17-live-091645 (PID 38604)
Dashboard    http://127.0.0.1:8080 (PID 19172)
Unit N1      online
Last status  uptime 1m 03s, Wi-Fi RSSI -53 dBm, fw 0.3.0, 6 s ago
Readings     ble 77.6/s, spectrum 0.0/s, status 0.1/s, rejected messages 0
Laptop clock 388 ms behind pool.ntp.org. WARNING: more than 100 ms off, latency results are not valid.
```
