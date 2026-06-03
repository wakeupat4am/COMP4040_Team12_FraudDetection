from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = PROJECT_ROOT / "end_to_end" / "artifacts" / "monitoring_log.jsonl"


class PipelineMonitor:
    def __init__(self) -> None:
        self.request_count = 0

    def log(self, payload: dict[str, Any]) -> None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {"logged_at": datetime.now(tz=timezone.utc).isoformat(), **payload}
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        self.request_count += 1
