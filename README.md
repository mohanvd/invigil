# Invigil

*Every signal leaves a trace.*

Invigil detects hidden cheating devices (phones, Bluetooth earpieces, smartwatches) in exam halls by listening passively to the 2.4 GHz band. One sensor unit, a Raspberry Pi Pico 2 W with an nRF24L01+PA+LNA radio, scans for Bluetooth advertisements and radio activity and sends its readings over Wi-Fi to a laptop. A machine learning model then decides what kind of device it is (phone, earpiece, smartwatch, or allowed) and how far it is from the unit (near, mid, or far). Seat zones and more units are Phase 2.

Grade 12 STEM capstone, team 12323, Egypt, 2026-2027.

## Repo layout

| Folder | What goes there |
| --- | --- |
| `firmware/` | Pico 2 W unit code (Pico SDK, C, CMake). In progress |
| `server/` | MQTT logger, fake data publisher, later the dashboard API |
| `ml/` | `features.py`, `label.py`, `train.py`, `synth.py`. See the [data collection protocol](docs/data-protocol.md) |
| `data/raw/` | Recorded sessions. Gitignored, never committed |
| `data/samples/` | Small anonymized samples that are safe to commit |
| `dashboard/` | Web app: live hall map and alerts |
| `simulation/` | Digital twin built from real calibration data |
| `docs/` | Diagrams, brand assets, and `results/` for every calibration or test run |

## Running the server tools

The server folder has two tools:

- **Logger** (`server/logger.py`): subscribes to the unit's topics and saves each valid reading to CSV.
- **Fake publisher** (`server/fake_publisher.py`): pretends to be the sensor unit (N1) and publishes readings that follow the [MQTT contract](docs/contract.md). Use it to work on the logger, dashboard and ML pipeline before the hardware is ready.

Run every command from the repo root.

### One-time setup

1. Install Python 3.11 or newer and [Mosquitto](https://mosquitto.org/download/). On Windows, the installer puts Mosquitto in `C:\Program Files\mosquitto` but does not add it to the PATH. Add that folder to the PATH so the `mosquitto`, `mosquitto_sub` and `mosquitto_passwd` commands below work.
2. Create a virtual environment and install the dependencies:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

   On macOS or Linux, activate with `source .venv/bin/activate` instead.
3. Create your config file from the template, then fill it in:

   ```bash
   copy server\config.toml.example server\config.toml
   ```

   On macOS or Linux, use `cp` and forward slashes. `server/config.toml` is gitignored because it holds the MQTT password and the hash salt. Without it, both tools connect to `localhost:1883` with no login, and the fake publisher picks a random salt for each run.

### Try it with fake data (no hardware needed)

You need a broker on `localhost:1883`. On Windows, the Mosquitto installer adds a service that already runs one, so you can skip to step 2. Otherwise, start one in its own terminal with `mosquitto -v`.

1. In terminal 1, start the logger. The session name becomes part of the output folder name:

   ```bash
   python -m server.logger --session fake-test
   ```

2. In terminal 2, start the fake unit:

   ```bash
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

### Using the real unit

The unit connects to the laptop over Wi-Fi, so the broker must listen on the network and require a password. The Windows Mosquitto service only listens on localhost, so stop it first (in a terminal run as administrator: `net stop mosquitto`). Then:

1. Create the password file (gitignored). It asks for a password:

   ```bash
   mosquitto_passwd -c server/mosquitto.passwd invigil
   ```

2. Start the broker with the project config:

   ```bash
   mosquitto -c server/mosquitto.conf -v
   ```

3. Put the same username and password in `server/config.toml` and in the firmware secrets. Point the unit at the laptop's IP address (find it with `ipconfig`).
4. If Windows Firewall asks, allow Mosquitto on private networks.
5. Start the logger as above.

### What the logger writes

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

### What the logger rejects

Every message is checked against the [MQTT contract](docs/contract.md) by `server/contract.py`. A message that fails is counted and its reason is printed once, but it is never written to disk. The logger rejects:

- topics other than `invigil/node/N1/{ble|spectrum|status}`, or a `node` field that does not match the topic
- missing or extra fields
- `ts` before 2020, which means the unit has not synced its clock yet or sent seconds instead of milliseconds
- `addr` that is not exactly 12 lowercase hex characters (so a raw MAC like `A9:1F:03:C2:D4:E8` is refused)
- `mfr` that is not `null` or a company ID like `"0x004C"`
- `hits` that is not 126 integers between 0 and `sweeps`
- decimal numbers or `true`/`false` where an integer is expected

### Tests

```bash
python -m pytest
```

This runs the tests in `server/` and `ml/`.

## Firmware (in progress)

The unit firmware is not written yet. The plan:

- Board: Raspberry Pi Pico 2 W (RP2350 + CYW43439 radio).
- Toolchain: the official Pico SDK in C with CMake, built with the Raspberry Pi Pico VS Code extension. The capstone bans Arduino and ESP boards, so the project uses neither, and no Arduino-Pico core.
- BLE: passive scan on the Pico's own radio using BTstack, observer only.
- 2.4 GHz sweep: nRF24L01+PA+LNA on SPI0, 126 channels, RPD hits. Receive only.
- Network: Wi-Fi and MQTT (lwIP MQTT app) to Mosquitto on the laptop, SNTP for timestamps.
- Wi-Fi and Bluetooth share the CYW43 radio, so scan windows and send windows alternate, as the [MQTT contract](docs/contract.md) requires.

### Wiring

Check each pin against the Pico 2 W pinout before soldering.

| nRF24L01+PA+LNA pin | Pico 2 W pin |
| --- | --- |
| VCC | 3V3(OUT). Never 5 V |
| GND | GND |
| SCK | GP18 |
| MOSI | GP19 |
| MISO | GP16 |
| CSN | GP17 |
| CE | GP20 |

Put a 100 uF capacitor across the radio's VCC and GND, close to the module.

### Planned modules

| Module | Job |
| --- | --- |
| `ble_scan` | BTstack passive scan, address hashing, boot-time test vector |
| `nrf_scan` | nRF24L01 channel sweep, RPD hit counts |
| `mqtt_link` | Broker connection, publishing, status messages |
| `config` | Settings from the gitignored secrets file, timing constants |
| `wifi_sta` | Wi-Fi station and SNTP clock |

### To measure on the real unit

These depend on hardware behavior, so they are tests to run, not numbers to assume:

- How long the scan window and send window should be, and how much quiet time is needed after the last publish before scanning restarts.
- How long one 126-channel sweep takes.
- Whether the unit's own Wi-Fi channel shows hits during scan windows.
- The byte order BTstack uses for addresses (see the test vector below).

## Address hashing test vector

The unit hashes every BLE address before sending it: `sha256(salt + 6 address bytes)`, keeping the first 12 hex characters. The salt is its UTF-8 bytes. The address bytes go most significant first, in the order the address is printed. `hash_addr` in `server/contract.py` is the reference.

The byte order BTstack hands addresses over in is not assumed. The firmware must reproduce this test vector at boot, and that is checked on real hardware:

| Input | Value |
| --- | --- |
| Salt | `invigil-test-vector` |
| Address as printed | `01:23:45:67:89:AB` |
| Bytes hashed | `invigil-test-vector` followed by `01 23 45 67 89 AB` |
| **Expected hash** | **`41239c0be85e`** |
| Hash with the wrong byte order | `5cebc32cde2c` |

If the unit prints `5cebc32cde2c`, the address bytes are reversed and the firmware must flip them before hashing.

The server test `test_shared_hash_vector` checks the same values. If you change them, change both.
