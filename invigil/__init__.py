"""One command for the whole laptop side: python -m invigil start|stop|status|calibrate.

Run from the repo root, or through invigil.bat.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Run state (PIDs, logs, calibration progress). Gitignored.
STATE_DIR = ROOT / ".invigil"
