# BTstack address byte order: 2026-10-26

The one-time check from [To measure](../../firmware.md#to-measure) in the firmware docs. **The byte order is correct.** The unit prints and hashes Bluetooth addresses in the usual order, the order phones and Windows show. `hash_bd_addr()` needs no change.

No raw addresses are in this report. The debug log was read in memory and never saved.

## Why it was needed

The boot self-check proves the hash code matches the [test vector](../../hashing.md#test-vector), but it feeds the address through BTstack's own text parser. It cannot show the order of the bytes BTstack hands over from a real advertisement. If that order were reversed, every published hash would be wrong.

## Method

1. Built a debug firmware with `INVIGIL_DEBUG_RAW_ADDR` set to 1, passed as a compiler flag in a separate gitignored build folder. `firmware/src/config.h` stayed at 0 and nothing debug was committed. The boot log showed the debug WARNING, and all four self-checks passed.
2. Ran the debug build on unit N1. It prints each device it hears as `debug: raw <address> -> hash <hash>`, at most once every 5 s per device.
3. At the same time, the laptop's own Bluetooth looked for nearby BLE devices with Windows' device search, for 90 s.
4. A script compared the two sets of addresses in memory, both as printed and reversed, and printed only counts.

The firmware docs suggest the nRF Connect phone app as the reference. The laptop was used instead because it could run the comparison for every device at once, without anyone copying an address by hand. To confirm that Windows writes addresses in the usual order, the script compared the laptop adapter's address inside the Windows device IDs with the adapter's physical address from Windows' network settings. They matched in the same order, not reversed.

## Result

| | Count |
| --- | --- |
| Distinct devices the laptop found | 10 |
| Distinct devices the unit printed | 18 |
| **Seen by both, same byte order** | **8** |
| Seen by both, only reversed | 0 |

8 of the 10 devices the laptop found were also printed by the unit, all in the same order and none reversed. The other 2 were not heard by the unit during the 90 s. The unit printed more devices than the laptop found because it scans continuously, while Windows' device search runs in rounds of about 30 s.

So `gap_event_advertising_report_get_address()` gives the address bytes in printed order, and `hash_bd_addr()` hashes them in the order [the hashing rule](../../hashing.md#the-rule) requires.

## Back to the normal firmware

The normal build (`INVIGIL_DEBUG_RAW_ADDR` 0) was flashed again, and its serial log was checked:

- The firmware image contains neither the raw-address print nor the debug warning text.
- After a fresh boot: no debug WARNING, all four self-checks PASS, MQTT connected.
- Over 45 s with 487 BLE readings captured: 0 address-shaped strings anywhere in the serial output.

The debug build folder was deleted afterwards so it cannot be flashed by mistake.

## Observation

One summary line in the normal-firmware run showed `mqtt_busy=8`, the number of times the unit waited for the MQTT output buffer to drain. Every earlier run showed 0. `send_overruns` and `ble_dropped` stayed at 0, so nothing was lost. Watch it in the longer window-timing run.
