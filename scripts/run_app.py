"""Run the local Signal Desk application."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.api.server import run


if __name__ == "__main__":
    run()
