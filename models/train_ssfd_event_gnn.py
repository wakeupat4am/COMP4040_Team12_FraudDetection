"""Train and evaluate an event-based GNN on the saved S-FFSD splits."""

from pathlib import Path

from train_ssfd_four_models import print_result, train_event_gnn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "models" / "ssfd_event_gnn"


def main() -> None:
    result = train_event_gnn(OUTPUT_DIR)
    print_result(result)


if __name__ == "__main__":
    main()
