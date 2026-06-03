from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FEEDBACK_PATH = PROJECT_ROOT / "end_to_end" / "artifacts" / "feedback.jsonl"


class FeedbackStore:
    def append(self, payload: dict[str, Any]) -> None:
        FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {"recorded_at": datetime.now(tz=timezone.utc).isoformat(), **payload}
        with FEEDBACK_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
