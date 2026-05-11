"""Train and evaluate a LightGBM baseline on the saved S-FFSD splits."""

import argparse
from pathlib import Path

from train_ssfd_four_models import print_result, train_lightgbm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "models" / "ssfd_lightgbm"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--use-unlabeled-context",
        action="store_true",
        help="Include earlier unlabeled rows when building history-based features.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = train_lightgbm(None, None, OUTPUT_DIR, use_unlabeled_context=args.use_unlabeled_context)
    print_result(result)


if __name__ == "__main__":
    main()
