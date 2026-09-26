# MQTT contract

Node IDs: `N1`, `N2`, `N3`. Timestamps: milliseconds since epoch (nodes sync with NTP).

```
invigil/node/{node_id}/ble
{ "ts": 1727340000123, "node": "N1", "addr": "a91f03c2d4e8", "rssi": -58, "mfr": "0x004C" }

invigil/node/{node_id}/spectrum
{ "ts": 1727340000123, "node": "N1", "sweeps": 50, "hits": [126 integers, one per channel] }

invigil/node/{node_id}/status
{ "ts": 1727340000123, "node": "N1", "uptime_s": 3600, "wifi_rssi": -61, "fw": "0.1.0" }
```

`mfr` is the Bluetooth SIG company ID as `"0x"` plus 4 uppercase hex digits, or `null` when the advertisement carries no manufacturer data.

Nodes must not scan the 2.4 GHz band while they are transmitting over Wi-Fi. Scan windows and send windows alternate, and readings taken during a send window are dropped.
