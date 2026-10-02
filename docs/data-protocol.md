# Data collection protocol

How to record the dataset for the two models: device type and distance band.
Follow it exactly. How the data is recorded decides whether the accuracy
number means anything.

## The rules that keep the score honest

1. **One test device per session.** The nRF24 sees the whole room, so its
   readings can only be tied to a device when one test device is on.
2. **Never move the device during a session.** One session = one device, one
   distance, one state, one position. Changing any of them means a new session.
3. **Label right after recording**, while you still remember what was on the desk.
4. **Test on whole sessions, never random rows.** `ml/train.py` already does
   this. Back-to-back windows are near copies, so a random split leaks the
   answers and gives a fake 99%.
5. **Seal a final test set.** Record one full round on a separate day, in a
   different room if possible, and do not train on it or even look at it until
   the model is finished. That is the number that goes on the poster.
6. **Use at least two different models per device type** where you can (two
   phones, two earpieces). With only one, the model learns "this AirPods", not
   "earpiece". Borrow devices from classmates.

## Labels

Device type (one per test device):

| Type | Meaning |
|---|---|
| `phone` | any smartphone |
| `earpiece` | Bluetooth earbuds or a single earpiece |
| `smartwatch` | smartwatch or fitness band |
| `allowed` | a device permitted in the hall (see open decision 1) |

Distance band, measured with a tape from the unit to the device:

| Band | Distance | Record at |
|---|---|---|
| `near` | under 1 m | 0.5 m |
| `mid` | 1 to 2 m | 1.5 m |
| `far` | 2 to 3.5 m | 3.0 m |

These band edges are a starting point. Adjust them after calibration shows
where RSSI actually separates.

## Device states and positions

Record each device in the states a cheater would really use:

| Type | States |
|---|---|
| phone | screen off idle, screen on, Bluetooth paired to an earpiece |
| earpiece | connected idle, streaming audio |
| smartwatch | on wrist, connected to phone |
| allowed | as it is normally used in the hall |

Positions: `desk`, `pocket`, `bag`. A body or a bag can cost several dB, so
the model must see all three.

## The session matrix

| | Count |
|---|---|
| Types | 4 |
| Bands | 3 |
| States (average) | 2 |
| Repeats (different positions or days) | 3 |
| **Sessions** | **about 72** |

At 3 minutes each, that is about 3.6 hours of recording, spread over
several days. Each 3-minute session gives about 175 windows, so about 12,000
rows in total.

Also record **empty-room baselines**: 3 minutes with no test device on, at the
start of every recording day. They set `ACTIVE_FRAC` in `ml/features.py`,
show which addresses are background, and give the false alarm rate for DR5.

## Session recipe

1. Turn off every test device that is not part of this session.
2. Place the device at the measured distance and position. Note the time.
3. Start the logger with a name that says what is happening:

   ```
   python -m server.logger --session earpiece-near-streaming-1
   ```

   Name format: `<type>-<band>-<state>-<repeat>`. Baselines: `baseline-<repeat>`.
4. Wait 3 minutes. Do not touch anything. Then press Ctrl+C.
5. Label it:

   ```
   python -m ml.label data/raw/<date>-earpiece-near-streaming-1
   ```

   This lists every address the unit heard, strongest first, and writes a
   `session.json` with the strongest one filled in. Check it is not an
   address from the baseline, then replace the `?` values:

   ```json
   {
     "name": "2026-10-20-earpiece-near-streaming-1",
     "notes": "left earbud only, case closed on desk",
     "devices": {
       "a91f03c2d4e8": {
         "type": "earpiece",
         "band": "near",
         "model": "earpiece A",
         "state": "streaming",
         "position": "desk"
       }
     }
   }
   ```

   If the device showed up under two addresses (address rotation), list both.
6. Check the features look sane:

   ```
   python -m ml.features data/raw/<date>-earpiece-near-streaming-1
   ```

## Training

```
python -m ml.train
```

It reads every session with a `session.json`, tests on held-out sessions, and
writes `docs/results/<date>-train/report.md` with the accuracy, the
confusion matrix, and the top features. To check the pipeline without real
data:

```
python -m ml.synth --out data/synthetic
python -m ml.train --data data/synthetic --name pipeline-check
```

The synthetic score only proves the code runs. Never report it.

## Privacy

- Only hashed addresses ever reach disk. `session.json` holds hashes, never
  raw MACs.
- Use `model` names like "earpiece A", not owners' names.
- `data/raw/` stays on the laptop. Only anonymized samples go in `data/samples/`.

## Open decisions

1. **What is `allowed`?** An invigilator's phone looks exactly like a
   student's phone over the air, so the model cannot learn the difference.
   The cleaner design may be: the model learns phone / earpiece / smartwatch,
   and "allowed" comes from a whitelist of known hashes. Decide this before
   recording the `allowed` sessions.
2. **Address rotation.** Phones and many earbuds change their BLE address
   every few minutes for privacy. That breaks hash whitelisting for those
   devices, and splits one device across several addresses in long sessions.
   Measure how often your test devices rotate in the first recordings.
3. **More BLE fields.** The contract only carries RSSI and the company ID.
   Apple phones and AirPods share the same company ID (`0x004C`), so the
   advertising interval and the spectrum have to separate them. The
   advertisement length or the first byte of the manufacturer data (Apple
   uses it as a message type) would help a lot, but it means changing the
   contract and the privacy rule about payloads. Decide after the first
   real recordings show whether accuracy is short.

## Questions only the hardware can answer

- Does an earpiece keep advertising while it streams audio?
- How long does one 126-channel sweep take, and how many sweeps fit in 5 s?
- What RSSI does each device give at 0.5, 1.5 and 3 m, and how much does a
  pocket or bag take off?
- Is `ACTIVE_FRAC` = 2% above the empty-room noise?
