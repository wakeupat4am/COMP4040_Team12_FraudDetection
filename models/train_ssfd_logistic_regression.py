"""Train and evaluate a regularized logistic regression baseline on S-FFSD."""

from pathlib import Path

from train_ssfd_four_models import print_result, train_logistic_regression


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "models" / "ssfd_logistic_regression"


def main() -> None:
    result = train_logistic_regression(None, None, OUTPUT_DIR)
    print_result(result)


if __name__ == "__main__":
    main()
