# Contributing to Invigil

Thanks for wanting to help. Invigil is a school capstone project, so the team is small and replies may take a few days.

By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Before you start

- For a bug or a small fix, open an issue or go straight to a pull request.
- For anything larger (a new feature, a change to the [MQTT contract](docs/contract.md), a new model output), open an issue first so we can agree on the approach.
- For a privacy or security problem, do not open a public issue. Follow [SECURITY.md](SECURITY.md).

## Setup

You need Python 3.11 or newer and [Mosquitto](https://mosquitto.org/download/). Run every command from the repo root.

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux and macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The full guide is in [docs/setup.md](docs/setup.md).

## Tests

```
python -m pytest
```

All tests must pass before you open a pull request. The same command runs in CI on Python 3.11, 3.12 and 3.13. If you change behavior, add or update a test for it.

## Privacy rules

These are not optional. A pull request that breaks one will be closed.

- Never commit raw captures. `data/raw/` is gitignored and stays on your machine.
- Never commit a raw MAC address, in data, code, tests, logs, screenshots or issue text. The only allowed addresses are the made-up ones already used in the tests and docs (for example `01:23:45:67:89:AB`).
- Never commit a hash salt, a Wi-Fi name or password, or MQTT credentials. Secrets live in gitignored files. Commit only the `*.example` templates.
- Data goes in `data/samples/` only after anonymizing: hashed addresses only, hashed with a salt you then throw away, no names of people or device owners, and no location details.
- Never store audio or packet payloads.
- If you commit a secret or raw data by mistake, tell us at once through [SECURITY.md](SECURITY.md). Deleting the file in a later commit does not remove it from history.

## Project rules

- **Receive only.** The nRF24L01 is used only as a receiver. We do not accept code that transmits to jam or interfere with any signal.
- **Firmware** uses the official Pico SDK in C with CMake. No Arduino, Arduino-Pico core, PlatformIO or ESP boards.
- **The models stay narrow.** They answer device type and distance band. Ask before adding classes, seat zones or multi-unit location.
- **Do not assume hardware behavior.** If something depends on range, thresholds, timing or byte order, say so and propose a test.
- **Results** from a calibration or test run go in `docs/results/YYYY-MM-DD-<name>/` with the raw summary, plots and a short note.
- **Writing:** plain, direct English in docs and UI text.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add spectrum features for hopping detection
fix: reject ts values sent in seconds
docs: explain the scan and send windows
test: cover empty spectrum windows
chore: update dependencies
```

Keep each commit to one change.

## Pull request flow

1. Fork the repo and create a branch from `main`, for example `fix/logger-timestamp`.
2. Make your change in small commits.
3. Run `python -m pytest`.
4. Update the docs if behavior, commands or formats changed.
5. Open a pull request against `main` and fill in the checklist.
6. A team member reviews it. CI must pass before it is merged.

## License

By contributing, you agree that your code is released under the [MIT license](LICENSE), and your documentation and images under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
