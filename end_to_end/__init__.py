"""End-to-end fraud detection product package."""

from __future__ import annotations

import os
from pathlib import Path


_ARTIFACT_ROOT = Path(__file__).resolve().parent / "artifacts"
_MPLCONFIGDIR = _ARTIFACT_ROOT / "mplconfig"
_MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_MPLCONFIGDIR))
