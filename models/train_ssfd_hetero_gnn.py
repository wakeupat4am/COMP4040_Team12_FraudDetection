"""Train and evaluate a heterogeneous GNN on the saved S-FFSD splits."""

from pathlib import Path

from train_ssfd_four_models import print_result, train_hetero_gnn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "models" / "ssfd_hetero_gnn"


def main() -> None:
    result = train_hetero_gnn(OUTPUT_DIR)
    print_result(result)


if __name__ == "__main__":
    main()
