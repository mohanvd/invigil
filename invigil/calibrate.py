"""Guided calibration: one device, 60 s at each distance from 0.5 to 3.5 m.

Each step is its own session folder in data/raw/, recorded with the logger's
Recorder and labelled with ml.label's session.json writer, so the contract
check and the label format are the ones the rest of the project uses.
Progress is saved after every step, so a stopped run picks up where it left off.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from invigil import STATE_DIR
from ml.features import BANDS, TYPES, load_ble
from ml.label import device_labels, summary, write_session_json
from server.config import Config
from server.logger import CsvSink, Recorder, now_ms, session_dir

DISTANCES = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5)
SECONDS = 60
POSITIONS = ("desk", "pocket", "bag")
HASH_RE = re.compile(r"[0-9a-f]{12}")


def band_for(distance_m: float) -> str:
    """near is under 1 m, mid is 1 to 2 m, far is over 2 m (docs/data-protocol.md)."""
    if distance_m < 1.0:
        return BANDS[0]
    if distance_m <= 2.0:
        return BANDS[1]
    return BANDS[2]


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not s:
        raise ValueError("the device name needs at least one letter or digit")
    return s


def step_key(distance_m: float) -> str:
    return f"{distance_m:g}"


def session_name(type_: str, name_slug: str, distance_m: float) -> str:
    return f"calib-{type_}-{name_slug}-{step_key(distance_m)}m"


@dataclass
class Progress:
    type: str
    name: str
    state: str
    position: str
    distances: list[float] = field(default_factory=lambda: list(DISTANCES))
    devices: list[str] = field(default_factory=list)  # hashed addresses of the test device
    steps: dict[str, str] = field(default_factory=dict)  # step_key -> finished session folder

    @staticmethod
    def path_for(type_: str, name: str, base: Path = STATE_DIR) -> Path:
        return base / f"calibration-{type_}-{slug(name)}.json"

    @classmethod
    def load(cls, path: Path) -> Progress | None:
        if not path.exists():
            return None
        return cls(**json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    def remaining(self) -> list[float]:
        return [d for d in self.distances if step_key(d) not in self.steps]


def move_aside(folder: Path) -> Path:
    """A folder from a step that was stopped halfway. Keep it, but out of the way."""
    target = folder.with_name(f"{folder.name}-incomplete-{datetime.now():%H%M%S}")
    folder.rename(target)
    return target


def choose_devices(table, known: list[str], ask: Callable[[str], str], say: Callable[[str], None]) -> list[str]:
    """Which hashed addresses in this step belong to the test device.

    The first step picks the strongest address and asks to confirm it. Later
    steps reuse it. If it is missing (the device changed its address), ask.
    """
    seen = [h for h in known if h in table.index]
    if seen:
        return seen
    say(table.head(5)[["advs", "rssi_median", "mfr"]].to_string())
    if known:
        say("The test device's address was not heard in this step. It may have changed address.")
        prompt = "Type its new hash from the list, or press Enter to leave this step unlabelled: "
        default = ""
    else:
        default = table.index[0]
        prompt = f"Test device hash [{default}]: "
    while True:
        answer = ask(prompt).strip().lower() or default
        if not answer:
            return []
        if HASH_RE.fullmatch(answer) and answer in table.index:
            return [answer]
        say("That hash is not in this step's list. Type one of the hashes shown.")


def label_step(folder: Path, progress: Progress, distance_m: float, hashes: list[str]) -> Path | None:
    devices = {
        h: {
            **device_labels(progress.type, band_for(distance_m), progress.name, progress.state, progress.position),
            "distance_m": distance_m,
        }
        for h in hashes
    }
    return write_session_json(folder, devices, notes=f"calibration step at {distance_m:g} m", kind="calibration")


def run(
    progress: Progress,
    progress_path: Path,
    record: Callable[[Path, int], None],
    ask: Callable[[str], str] = input,
    say: Callable[[str], None] = print,
    out_base: Path = Path("data/raw"),
    seconds: int = SECONDS,
) -> None:
    """Step through every distance not done yet. record(folder, seconds) records one step."""
    name_slug = slug(progress.name)
    for d in progress.remaining():
        folder = session_dir(out_base, session_name(progress.type, name_slug, d))
        while True:
            answer = ask(f"\nPlace the device at {d:g} m ({band_for(d)}), then press Enter. Type q to stop: ")
            if answer.strip().lower() == "q":
                say("Stopped. Run calibrate again with the same type and name to continue.")
                return
            if folder.exists():
                say(f"Moved an unfinished recording aside: {move_aside(folder)}")
            say(f"Recording {seconds} s into {folder} ...")
            record(folder, seconds)
            table = summary(folder)
            if not table.empty:
                break
            say("No BLE readings in this step. Is the unit online? Try the step again.")

        hashes = choose_devices(table, progress.devices, ask, say)
        for h in hashes:
            if h not in progress.devices:
                progress.devices.append(h)
        if hashes:
            label_step(folder, progress, d, hashes)
        else:
            say("This step has no session.json, so training will skip it.")
        progress.steps[step_key(d)] = str(folder)
        progress.save(progress_path)
        say(f"Step {d:g} m done.")
    say("\n" + results_table(progress))


def results_table(progress: Progress) -> str:
    rows = [f"{'distance':>8}  {'band':<4}  {'readings':>8}  {'median RSSI':>11}"]
    for d in progress.distances:
        folder = progress.steps.get(step_key(d))
        if folder is None:
            rows.append(f"{d:>7g}m  {band_for(d):<4}  {'not recorded':>22}")
            continue
        ble = load_ble(Path(folder))
        mine = ble[ble["addr"].isin(progress.devices)] if not ble.empty else ble
        if mine.empty:
            rows.append(f"{d:>7g}m  {band_for(d):<4}  {0:>8}  {'-':>11}")
        else:
            rows.append(f"{d:>7g}m  {band_for(d):<4}  {len(mine):>8}  {mine['rssi'].median():>7.1f} dBm")
    return "\n".join(rows)


def mqtt_recorder(cfg: Config) -> tuple[Callable[[Path, int], None], Callable[[], None]]:
    """A record(folder, seconds) function that records the unit over MQTT, and a close function."""
    from invigil import monitor

    lock = threading.Lock()
    current: list[Recorder | None] = [None]

    def on_message(topic, payload):
        with lock:
            if current[0] is not None:
                current[0].handle(topic, payload, now_ms())

    client, ready, errors = monitor.connect(cfg, on_message, "calibrate")
    if not ready.wait(5):
        monitor.close(client)
        reason = errors[0] if errors else f"no answer from {cfg.host}:{cfg.port}"
        raise SystemExit(f"Cannot reach the broker ({reason}). Run: python -m invigil start")

    def record(folder: Path, seconds: int) -> None:
        recorder = Recorder(CsvSink(folder))
        with lock:
            current[0] = recorder
        try:
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                time.sleep(min(1.0, end - time.monotonic()))
        finally:
            with lock:
                current[0] = None
            recorder.close()

    return record, lambda: monitor.close(client)


def ask_choice(ask: Callable[[str], str], prompt: str, choices: tuple[str, ...]) -> str:
    while True:
        answer = ask(f"{prompt} ({' / '.join(choices)}): ").strip().lower()
        if answer in choices:
            return answer
        print(f"Type one of: {', '.join(choices)}")


def setup(args, ask: Callable[[str], str] = input) -> tuple[Progress, Path]:
    """Ask for whatever the command line did not give, and load saved progress."""
    type_ = args.type or ask_choice(ask, "Device type", TYPES)
    if type_ not in TYPES:
        raise SystemExit(f"type must be one of {', '.join(TYPES)}")
    name = args.name or ""
    while not name:
        name = ask("Device name, for example 'earpiece A' (never a person's name): ").strip()
    path = Progress.path_for(type_, name)
    saved = Progress.load(path)
    if saved is not None:
        print(f"Continuing the run for {type_} '{saved.name}': {len(saved.steps)} of {len(saved.distances)} steps done.")
        return saved, path
    state = args.state or ask("State, for example 'streaming' or 'screen off idle': ").strip()
    position = args.position or ask_choice(ask, "Position", POSITIONS)
    progress = Progress(type_, name, state, position)
    progress.save(path)
    return progress, path
