"""End-to-end pipeline contract and score orchestration skeleton."""

from __future__ import annotations

import json
from pathlib import Path
from fraud_detection.scoring import score_payload


def demo() -> None:
    project_root = Path(__file__).resolve().parents[1]
    example = json.loads(
        (project_root / "end_to_end" / "example_input.json").read_text(encoding="utf-8")
    )
    output = score_payload(example)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    demo()
