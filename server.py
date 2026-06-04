from __future__ import annotations

import sys
from pathlib import Path

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


if __name__ == "__main__":
    uvicorn.run("fraud_detection.api:app", host="0.0.0.0", port=8000, reload=False)
