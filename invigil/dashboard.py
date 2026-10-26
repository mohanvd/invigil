"""Build the dashboard and serve it locally over http.

The hosted dashboard is HTTPS, and a browser blocks a plain ws:// connection
from an HTTPS page, so the hosted demo cannot reach ws://<laptop>:9001. The
launcher serves its own build over http on localhost instead.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode

from invigil import ROOT

DASHBOARD = ROOT / "dashboard"
DIST = DASHBOARD / "dist"
PORT = 8080
SOURCES = ("src", "public", "index.html", "package.json", "pnpm-lock.yaml", "vite.config.ts", "tsconfig.app.json")


def newest_source(base: Path = DASHBOARD) -> float:
    newest = 0.0
    for name in SOURCES:
        path = base / name
        if path.is_dir():
            for f in path.rglob("*"):
                if f.is_file():
                    newest = max(newest, f.stat().st_mtime)
        elif path.exists():
            newest = max(newest, path.stat().st_mtime)
    return newest


def needs_build(base: Path = DASHBOARD) -> bool:
    index = base / "dist" / "index.html"
    return not index.exists() or index.stat().st_mtime < newest_source(base)


def needs_install(base: Path = DASHBOARD) -> bool:
    return not (base / "node_modules").is_dir()


def pnpm() -> list[str] | None:
    for name in ("pnpm", "corepack"):
        found = shutil.which(name)
        if found:
            return [found] if name == "pnpm" else [found, "pnpm"]
    return None


def build_env() -> dict:
    # A local build is never the demo-only public site.
    env = dict(os.environ)
    env.pop("VITE_DEMO_ONLY", None)
    return env


def run_pnpm(args: list[str]) -> int:
    cmd = pnpm()
    if cmd is None:
        print("pnpm is not installed. Install Node.js 24, then run: corepack enable")
        return 1
    return subprocess.run([*cmd, *args], cwd=DASHBOARD, env=build_env()).returncode


def serve_cmd(port: int = PORT) -> list[str]:
    return [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(DIST)]


def live_url(port: int, broker_url: str, username: str) -> str:
    """The page that opens the dashboard in Live mode.

    The password is never put in the URL. The dashboard asks for it once per tab.
    """
    query = urlencode({"source": "live", "broker": broker_url, "user": username})
    return f"http://127.0.0.1:{port}/?{query}#/live"
