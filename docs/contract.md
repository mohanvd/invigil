# MQTT contract

Node IDs: `N1` (one sensor unit). Timestamps: milliseconds since epoch (the unit syncs with SNTP).

```
invigil/node/{node_id}/ble
{ "ts": 1727340001000, "node": "N1", "readings": [
    { "ts": 1727340000123, "addr": "a91f03c2d4e8", "rssi": -58, "mfr": "0x004C" },
    { "ts": 1727340000410, "addr": "0f5e2b7a91c4", "rssi": -81, "mfr": null }
] }

invigil/node/{node_id}/spectrum
{ "ts": 1727340000123, "node": "N1", "sweeps": 50, "hits": [126 integers, one per channel] }

invigil/node/{node_id}/status
{ "ts": 1727340000123, "node": "N1", "uptime_s": 3600, "wifi_rssi": -61, "fw": "0.1.0" }
```

## BLE readings

The unit does not send one message per advertisement. After each scan window it sends the readings from that window together, in one or more `ble` messages.

| Field | Meaning |
| --- | --- |
| `ts` | End of the scan window the message was sent after, ms since epoch. |
| `node` | The unit. Must match the topic. |
| `readings` | One or more readings, oldest first. Each one is a single advertisement. |

Each reading:

| Field | Meaning |
| --- | --- |
| `ts` | When the advertisement was heard, ms since epoch. |
| `addr` | The hashed address: 12 lowercase hex chars ([hashing](hashing.md)). |
| `rssi` | Signal strength in dBm, an integer from -127 to 0. |
| `mfr` | The Bluetooth SIG company ID as `"0x"` plus 4 uppercase hex digits, or `null` when the advertisement carries no manufacturer data. |

A reading that did not fit in the send window is sent after the next scan window, so its `ts` can be older than that window.

**Size limit.** The unit keeps every `ble` payload at or under **1400 bytes**, and starts another message when the next reading would go over. A reading is at most 69 bytes, so a message carries at least 19 readings, usually about 20. Why 1400:

- **lwIP.** The unit's MQTT client only accepts a publish when the whole packet fits in its output buffer at once (`MQTT_OUTPUT_RINGBUF_SIZE`, 8 KB in `firmware/src/lwipopts.h`). 1400 bytes leaves room for the spectrum message and several `ble` messages queued together.
- **One TCP segment.** A TCP segment carries at most 1460 bytes (`TCP_MSS`). 1400 bytes of payload plus the MQTT header and topic (at most 38 bytes, even with a 16-char node ID) fits in one segment, so each message leaves the unit as a single Wi-Fi frame, and a lost frame resends one message, not part of two.
- **Broker and dashboard.** Mosquitto has no message size limit by default (MQTT allows up to 256 MB), and paho and the browser client have none either, so 1400 bytes is far inside every limit on the laptop.

The logger still writes one row per reading to `ble.csv`, with the same columns as before (`rx_ts, ts, node, addr, rssi, mfr`).

## Spectrum

`ts` in a spectrum message is the end of the scan window its sweeps came from.

## Rules

The unit must not scan the 2.4 GHz band while it is transmitting over Wi-Fi. Scan windows and send windows alternate, and readings taken during a send window are dropped.

The topic keeps the `{node_id}` level so more units can be added in Phase 2 without changing the format.

## Transports

The unit publishes over plain MQTT on port 1883. The dashboard runs in a browser, which cannot open a plain MQTT socket, so it subscribes to `invigil/node/+/+` over WebSockets on port 9001 (see `server/mosquitto.conf`). Topics and payloads are the same on both.

## Proposed

Not implemented. Nothing publishes this topic yet, `server/contract.py` rejects it, and the dashboard only shows detections from its Demo source. Agree on it here before building the Python side.

The model runs on the laptop, not on the unit. Once per decision window it publishes one message for each device it has an answer for:

```
invigil/node/{node_id}/detection
{ "ts": 1727340005000, "node": "N1", "addr": "a91f03c2d4e8", "type": "earpiece", "type_conf": 0.91, "band": "near", "band_conf": 0.84, "rssi": -52 }
```

| Field | Meaning |
| --- | --- |
| `ts` | End of the decision window, ms since epoch, on the unit's clock (the `ts` of the last reading used). `rx_ts - ts` at the dashboard is then the alert latency of design requirement 4. |
| `node` | The unit whose readings were used. Must match the topic. |
| `addr` | The 12-char hashed address, or `null` when the device was only seen in the spectrum scan (an earpiece that streams audio without advertising). |
| `type` | `phone`, `earpiece`, `smartwatch` or `allowed`. |
| `type_conf` | Model confidence in `type`, from 0 to 1. |
| `band` | `near`, `mid` or `far`. |
| `band_conf` | Model confidence in `band`, from 0 to 1. |
| `rssi` | Median RSSI over the window in dBm, an integer from -127 to 0, or `null` when there were no BLE readings. |

Rules:

- The topic keeps the `invigil/node/{node_id}/...` format, so the dashboard's existing subscription already receives it.
- One message per device per window. A device that is still there is reported again in the next window, so the dashboard can tell when it leaves. The dashboard keeps one alert per device and updates it.
- `allowed` devices are reported too, so the hall map can show them. They never raise an alert.
- Same privacy rule as the rest of the contract: hashed addresses only, no payload bytes.

Open questions:

- Window length. 5 s matches design requirement 1 but has to be checked against how many sweeps fit in a window on the real unit.
- With `addr` set to `null`, two spectrum-only devices of the same type cannot be told apart. Whether that matters depends on how the earpiece behaves on real hardware (see `docs/data-protocol.md`).
- Whether `allowed` comes from the model or from a whitelist of hashes (open decision 1 in `docs/data-protocol.md`). The payload is the same either way.
