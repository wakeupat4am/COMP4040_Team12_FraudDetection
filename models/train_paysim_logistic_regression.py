"""Train and evaluate a regularized logistic regression baseline on PaySim."""

from pathlib import Path

from train_paysim_four_models import load_saved_splits, print_result, train_logistic_regression


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "models" / "paysim_logistic_regression"


def main() -> None:
    train_df, val_df, test_df = load_saved_splits()
    result = train_logistic_regression(train_df, val_df, test_df, OUTPUT_DIR)
    print_result(result)


if __name__ == "__main__":
    main()
