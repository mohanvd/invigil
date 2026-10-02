# Setup and operation

How to install the laptop tools, run them with fake data, connect the real unit, and read what the logger writes. Run every command from the repo root.

The server folder has two tools:

- **Logger** (`server/logger.py`): subscribes to the unit's topics and saves each valid reading to CSV.
- **Fake publisher** (`server/fake_publisher.py`): pretends to be the sensor unit (N1) and publishes readings that follow the [MQTT contract](contract.md). Use it to work on the logger, dashboard and ML pipeline before the hardware is ready.

## One-time setup

1. Install Python 3.11 or newer and [Mosquitto](https://mosquitto.org/download/). On Windows, the installer puts Mosquitto in `C:\Program Files\mosquitto` but does not add it to the PATH. Add that folder to the PATH so the `mosquitto`, `mosquitto_sub` and `mosquitto_passwd` commands below work.
2. Create a virtual environment and install the dependencies (Windows PowerShell):

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   On Linux or macOS, use `python3 -m venv .venv` and activate with `source .venv/bin/activate`.
3. Create your config file from the template, then fill it in:

   ```powershell
   Copy-Item server\config.toml.example server\config.toml
   ```

   On Linux or macOS: `cp server/config.toml.example server/config.toml`.

   `server/config.toml` is gitignored because it holds the MQTT password and the hash salt. Without it, both tools connect to `localhost:1883` with no login, and the fake publisher picks a random salt for each run.

## Try it with fake data (no hardware needed)

You need a broker on `localhost:1883`. On Windows, the Mosquitto installer adds a service that already runs one, so you can skip to step 1. Otherwise, start one in its own terminal with `mosquitto -v`.

1. In terminal 1, start the logger. The session name becomes part of the output folder name:

   ```powershell
   python -m server.logger --session fake-test
   ```

2. In terminal 2, start the fake unit:

   ```powershell
   python -m server.fake_publisher
   ```

The fake publisher prints the ground truth for the run: each fake device's hashed address, its type, its distance band, and its distance from the unit. Every 10 seconds the logger prints how many messages it got from the unit, the latency, and how many messages it rejected. Press Ctrl+C in each terminal to stop.

Useful options (add `--help` to either command to see all of them):

| Command | Option | What it does |
| --- | --- | --- |
| logger | `--session NAME` | Output folder is `data/raw/<date>-NAME/`. Reusing a name appends to it. |
| logger | `--out DIR` | Write somewhere other than `data/raw/` |
| both | `--host`, `--port` | Override the broker address from the config |
| fake | `--duration 60` | Stop after 60 seconds |
| fake | `--seed 1` | Same fake devices and readings every run |
| fake | `--scan-ms`, `--send-ms`, `--sweeps` | Change the scan and send window timing |

To watch the raw messages on the broker, run `mosquitto_sub -t "invigil/#" -v`.

**The fake data has the right shape, not the right physics.** The distances, signal strengths, and device behavior in `server/fake_publisher.py` are placeholders marked as guesses. Replace them with calibration results, and never train the final models on fake data.

## Using the real unit

The unit connects to the laptop over Wi-Fi, so the broker must listen on the network and require a password. The Windows Mosquitto service only listens on localhost, so stop it first (in a terminal run as administrator: `net stop mosquitto`). Then:

1. Create the password file (gitignored). It asks for a password:

   ```powershell
   mosquitto_passwd -c server/mosquitto.passwd invigil
   ```

2. Start the broker with the project config:

   ```powershell
   mosquitto -c server/mosquitto.conf -v
   ```

3. Put the same username and password in `server/config.toml` and in the firmware secrets. Point the unit at the laptop's IP address (find it with `ipconfig`, or `ip addr` on Linux).
4. If Windows Firewall asks, allow Mosquitto on private networks.
5. Start the logger as above.

## What the logger writes

Each session folder holds three CSV files, one per message type:

| File | Columns |
| --- | --- |
| `ble.csv` | `rx_ts, ts, node, addr, rssi, mfr` |
| `spectrum.csv` | `rx_ts, ts, node, sweeps, ch000 ... ch125` |
| `status.csv` | `rx_ts, ts, node, uptime_s, wifi_rssi, fw` |

- `ts` is when the unit took the reading. `rx_ts` is when the laptop received it. Both are milliseconds since epoch, so `rx_ts - ts` is the unit-to-laptop latency (design requirement 4). The two clocks are only as close as SNTP keeps them, so check the clock offset before you report a latency result. A negative latency means the unit clock is ahead.
- Fake runs show `fw` as `0.1.0-fake` in `status.csv`.
- Files are flushed after every row, so a crash or Ctrl+C loses nothing.

Load a session with pandas:

```python
import pandas as pd
ble = pd.read_csv("data/raw/2026-09-27-fake-test/ble.csv")
```

## What the logger rejects

Every message is checked against the [MQTT contract](contract.md) by `server/contract.py`. A message that fails is counted and its reason is printed once, but it is never written to disk. The logger rejects:

- topics other than `invigil/node/N1/{ble|spectrum|status}`, or a `node` field that does not match the topic
- missing or extra fields
- `ts` before 2020, which means the unit has not synced its clock yet or sent seconds instead of milliseconds
- `addr` that is not exactly 12 lowercase hex characters (so a raw MAC like `A9:1F:03:C2:D4:E8` is refused)
- `mfr` that is not `null` or a company ID like `"0x004C"`
- `hits` that is not 126 integers between 0 and `sweeps`
- decimal numbers or `true`/`false` where an integer is expected

## Tests

```powershell
python -m pytest
```

This runs the tests in `server/` and `ml/`.

## Checking the ML pipeline

```powershell
python -m ml.synth
python -m ml.train --data data/synthetic
```

`ml.synth` writes fake sessions to `data/synthetic/` (gitignored). `ml.train` tests on held-out sessions and writes a report to `docs/results/<date>-train/`. The synthetic score only proves the code runs. Never report it. Recording the real dataset is covered in the [data collection protocol](data-protocol.md).
