# Model v2: device type and near / not near

Date: 2026-11-23. Data: the same 24 labelled calibration sessions as the [first model](../2026-11-22-first-model/report.md), recorded on 2026-11-22. No new recordings.

What changed after the first model:

- **Two modes.** Watch mode: the unit on the invigilator's desk reports banned devices in the hall and their type. Search mode: the invigilator carries the unit along the rows, and a near alert marks the seat.
- **Two bands instead of three.** near (under 1 m) and not near. The first model showed that RSSI from one unit cannot tell 1.5 m from 3.5 m indoors. Sessions labelled `mid` or `far` are now `not_near`. The 1 m sessions are `not_near` (an edge belongs to the farther band).
- **The distance model sees RSSI only:** median, mean, spread, minimum and maximum of the device's own signal strength in the window. No spectrum features (they followed the room's Wi-Fi load) and no manufacturer or advertising-timing features (see below).
- **Design requirement 3** is now near / not-near accuracy, at least 80% on held-out sessions.

Files in this folder:

- `make_checks.py`: makes everything below from `data/raw/` (run from the repo root) and saves both models to `ml/models/` (gitignored), where the detector loads them.
- `train_output.md`: the standard `ml.train` report.
- `confusion_type.csv`, `confusion_band.csv`: the confusion matrices.
- `checks.txt`: the extra checks quoted below.
- `response_time.csv`: each session replayed through the detector.

## Summary

| | Result on unseen sessions | Target | |
| --- | --- | --- | --- |
| Device type (DR2) | 100.0% | 85% | Passes on paper. One earpiece brand, no smartwatch, no allowed device: not yet a real result |
| Near / not near (DR3) | 89.6% (84.2% balanced) | 80% | Passes. 76% of near windows found, 7% of not-near windows called near |
| Response time (DR1) | median 1.9 s, 15 of 19 detected sessions within 5 s | 5 s | From recorded sessions, not a live switch-on test |

Accuracy alone flatters the near / not-near model: only 220 of the 1256 windows are near, so a model that always answered "not near" would score 82.5%. Read the near recall and the balanced accuracy (the mean of near recall and not-near recall) next to it. I suggest stating DR3 as balanced accuracy for the poster.

## How it was tested

Whole sessions are held out, never single windows. `ml.train` splits the 24 sessions into 5 groups and tests each group with a model trained on the other four. `checks.txt` adds leave one session out (24 folds) and leave one device out (4 folds: the model never saw the device it is tested on).

| Device | Distances | Windows | Type |
| --- | --- | --- | --- |
| Phone B (fab lab iPhone) | 0.5 to 3.5 m, 7 sessions | 385 | phone |
| Phone B class (iPhone) | 0.5, 1, 1.5 m | 164 | phone |
| Phone C class (Android, nRF Connect) | 0.5 to 3.5 m, 7 sessions | 327 | phone |
| Earpiece B class (Oraimo, case open) | 0.5 to 3.5 m, 7 sessions | 380 | earpiece |

## Device type

Accuracy on unseen sessions **100.0%**, on training data 100.0%. Every banned device was flagged as banned.

| true \ predicted | phone | earpiece |
| --- | --- | --- |
| phone | 876 | 0 |
| earpiece | 0 | 380 |

Top features: `mfr_oraimo` 0.273, `n_adv` 0.195, `adv_interval_ms` 0.183, `mfr_apple` 0.076, `mfr_none` 0.047, `spec_active` 0.043.

The model is unchanged from the first run and keeps all features, spectrum included. It scores 100% without the spectrum features too, and 96.9% with neither spectrum nor manufacturer (`checks.txt`). The 100% means "Oraimo is an earpiece, the others are phones": the only earpiece is the only Oraimo device, and it advertises about 1.5 times a second against 2.7 to 6.4 for the phones. Leave one device out cannot be run for type, because there is only one earpiece.

## Near / not near

Accuracy on unseen sessions **89.6%**, on training data 98.0%.

| true \ predicted | near | not near |
| --- | --- | --- |
| near | 167 | 53 |
| not near | 77 | 959 |

| Split | Accuracy | Balanced | Near found | Not near called near |
| --- | --- | --- | --- | --- |
| 5 groups of sessions (`ml.train`) | 89.6% | 84.2% | 75.9% | 7.4% |
| Leave one session out | 89.7% | 84.5% | 76.4% | 7.4% |
| Leave one device out | 90.6% | 84.5% | 75.0% | 6.1% |

The three splits agree, which they did not for the first model. Top features: `rssi_median` 0.407, `rssi_mean` 0.319, `rssi_max` 0.175, `rssi_min` 0.082, `rssi_std` 0.017.

Share of windows called near, per device and distance (leave one session out):

| Device | 0.5 m | 1 m | 1.5 m | 2 m | 2.5 m | 3 m | 3.5 m |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Earpiece B class | 49% | 27% | 0% | 11% | 0% | 2% | 0% |
| Phone B | 95% | 100% | 0% | 0% | 0% | 0% | 0% |
| Phone B class | 69% | 0% | 0% | | | | |
| Phone C class | 93% | 0% | 0% | 0% | 0% | 0% | 0% |

- Past 1 m it almost never says near: 9 of 817 windows at 1.5 m and farther (1.1%).
- Most errors are at the 1 m edge. Phone B at 1 m reads -67 dBm, as strong as at 0.5 m, so all 55 of its windows are called near and count as wrong. Without the 1 m sessions, accuracy is 97.6% (95.8% balanced).
- The earpiece is the weak case: only 49% of its 0.5 m windows are called near. Its window RSSI at 0.5 m spreads from about -71 to -56 dBm, so a single 5 s window often looks like 1 m or more. In search mode the invigilator stands at a seat for a few seconds, so the banner gets several chances per seat. That is not measured yet.

### Why RSSI only

With manufacturer and timing features added, the model learned which device it was looking at instead of how far away it was. Six of the earpiece's seven sessions are not near, so "Oraimo" came to mean "not near", and only 7% of the earpiece's 0.5 m windows were called near. Leave one session out, same data:

| Distance model features | Accuracy | Balanced | Near found |
| --- | --- | --- | --- |
| RSSI only (used) | 89.7% | 84.5% | 76.4% |
| RSSI and advertising timing | 87.7% | 79.7% | 67.3% |
| RSSI, timing and manufacturer | 85.6% | 73.5% | 55.0% |

## Response time

**Not measured live.** Design requirement 1 starts the clock when a device starts transmitting. That needs someone to switch a device on next to the running unit, and on 2026-11-23 the unit and the broker were not running. What was measured instead is a replay: each recorded session fed through `server/detector.py` in the order its messages reached the laptop, deciding when the live detector would (50 ms after each BLE batch arrives, and at least once a second), with models trained on the other 23 sessions. The clock starts at the first advertisement of the test device in the session. The device was already on when the recording started, so this leaves out the time from switch-on to the first advertisement.

| | Sessions | Median | Within 5 s |
| --- | --- | --- | --- |
| First alert for the device | 19 of 24 detected | 1.9 s | 15 of 19 |
| First alert with the right type | 19 of 24 | 1.9 s | 15 of 19 |
| First alert with the right type and the right near / not near | 18 of 24 | 2.6 s | 14 of 19 |

Per session in `response_time.csv`.

- **Five sessions never alert:** phone C at 1.5 m and farther. Its median RSSI there is -92 to -99 dBm, below the -85 dBm cut-off. That is the cut-off working as designed, and it is a range problem (DR6), not a speed problem.
- **Four alerts took 5.7 to 7.9 s:** phone B at 2, 2.5 and 3.5 m, and phone B class at 1.5 m. In their first seconds the median RSSI was -86 to -90 dBm, just under the cut-off. For phone B at 2 m it rose above -85 dBm 7 s in. A lower cut-off makes these faster and lets in more devices from neighbouring rooms. The baseline in the real hall should decide it.
- **Phone B at 1 m** was always called near (see above), so it never got a right near / not-near answer.
- `first_heard_to_laptop_s` in the CSV is the arrival time minus the unit's timestamp. Some values are negative: the laptop clock and the unit's clock were up to 0.4 s apart that day, so treat sub-second numbers as rough.

To measure DR1 live:

1. `invigil start` with the unit running, and note the laptop clock offset on the status screen (under 100 ms).
2. Put a phone 0.5 m from the unit with Bluetooth off. Wait 30 s.
3. Turn Bluetooth on and note the laptop time to the second (or film the phone and the dashboard together).
4. Note when the alert appears on the dashboard. The logger also writes `detection.csv` with `rx_ts` for every detection.
5. Repeat 10 times per device type and distance (0.5 m and 3 m), and report the median and the worst.

## Limits

Read every number above with these in mind:

- **One earpiece brand.** The only earpiece is one pair of Oraimo buds, case open. The type model has not seen any other earpiece and cannot be tested on one.
- **No smartwatch and no allowed device.** The Huawei watch was not heard while connected to its phone. `allowed` now comes from the whitelist in `server/config.toml`, not from the model, so it needs no training data, but nothing has tested it on hardware.
- **One room, one afternoon, one position.** All 24 sessions are 60 s, on the desk, in the fab lab, recorded in distance order on 2026-11-22. Nothing was in a pocket or a bag, and no other bodies were between the device and the unit.
- **Few sessions.** One session per device per distance, 4 near sessions in total. A different phone or a different room can move these numbers a lot.
- **Phone C is weak.** Past 1 m its median RSSI is below the detector's -85 dBm cut-off, so the detector does not report it at all (see Response time). That is also a design requirement 6 (range) problem.
- **No final test set.** The protocol asks for a sealed set from another day or room. None exists yet, so none of these is a poster number.

## What runs live now

- `server/detector.py` loads both models and publishes `invigil/node/N1/detection` with `near` or `not_near` ([contract](../../contract.md#detections)). `invigil start` starts it when `ml/models/` has the models.
- Devices weaker than -85 dBm (median over 5 s) are ignored. In the empty-room baseline no device had a median above -86 dBm. The real hall needs its own baseline (DR5).
- The whitelist is `[whitelist] allowed` in `server/config.toml`, hashes only.
- The dashboard's Live page shows the alerts with their type, and a large `NEAR: <type>` banner while a banned device has been called near in the last 3 s.
- End to end with the fake publisher on a local broker: an alert on new readings reached a subscriber 0.8 s (median) and at most 1.4 s after the reading's timestamp (44 detections, 20 s run). The real unit adds its Wi-Fi delay: 590 ms median BLE latency in the [2026-10-27 batch test](../2026-10-27-ble-batches/report.md).
