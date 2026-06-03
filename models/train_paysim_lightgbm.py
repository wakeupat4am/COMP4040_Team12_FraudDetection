"""Train and evaluate a LightGBM baseline on the saved PaySim splits."""

from pathlib import Path

from train_paysim_four_models import load_saved_splits, print_result, train_lightgbm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "models" / "paysim_lightgbm"


def main() -> None:
    train_df, val_df, test_df = load_saved_splits()
    result = train_lightgbm(train_df, val_df, test_df, OUTPUT_DIR)
    print_result(result)


if __name__ == "__main__":
    main()
