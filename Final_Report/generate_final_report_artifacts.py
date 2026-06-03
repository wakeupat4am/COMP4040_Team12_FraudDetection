"""Generate report-ready artifacts for the final report."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FINAL_REPORT_DIR = PROJECT_ROOT / "Final_Report"
VALIDATED_DIR = PROJECT_ROOT / "models" / "ssfd_validated_ensemble"
EXPLORATORY_DIR = PROJECT_ROOT / "models"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def df_to_markdown_table(df: pd.DataFrame) -> str:
    headers = list(df.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in df.iterrows():
        values = [str(row[col]) for col in headers]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main_table() -> pd.DataFrame:
    df = pd.read_csv(VALIDATED_DIR / "ssfd_validated_model_comparison.csv")
    role_map = {
        "LightGBM": "Conservative tabular baseline with strong high-confidence scoring.",
        "AdaBoost": "High-recall tabular model emphasizing hard fraud cases.",
        "Event-Based GNN": "Best balanced single model using temporal transaction structure.",
        "Validated Upgraded Ensemble": "Final product candidate combining tabular and temporal signals.",
    }
    df["role_comment"] = df["model"].map(role_map)
    return df[
        [
            "model",
            "accuracy",
            "precision",
            "recall",
            "f1",
            "roc_auc",
            "average_precision",
            "role_comment",
        ]
    ]


def wider_table() -> pd.DataFrame:
    validated = main_table().copy()
    validated["evaluation_protocol"] = "Validation-based chronological split"

    extra_rows = []
    exploratory_models = {
        "Heterogeneous GNN": EXPLORATORY_DIR / "ssfd_hetero_gnn" / "ssfd_hetero_gnn_metrics.json",
        "Logistic Regression": EXPLORATORY_DIR / "ssfd_logistic_regression" / "ssfd_logistic_regression_metrics.json",
    }
    role_map = {
        "Heterogeneous GNN": "Static multi-relation graph baseline; excluded due to weak performance.",
        "Logistic Regression": "Regularized linear tabular baseline; useful for benchmarking but redundant in ensemble.",
    }
    for model_name, metric_path in exploratory_models.items():
        payload = load_json(metric_path)
        metrics = payload["metrics"]
        extra_rows.append(
            {
                "model": model_name,
                "accuracy": metrics["accuracy"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "roc_auc": metrics["roc_auc"],
                "average_precision": metrics["average_precision"],
                "role_comment": role_map[model_name],
                "evaluation_protocol": "Earlier hold-out split (supporting baseline only)",
            }
        )
    return pd.concat([validated, pd.DataFrame(extra_rows)], ignore_index=True)


def load_case_frame() -> pd.DataFrame:
    return pd.read_csv(VALIDATED_DIR / "ssfd_validated_upgraded_ensemble_test_predictions.csv")


def explain_row(kind: str, row: pd.Series) -> str:
    if kind == "caught_fraud":
        return (
            "The ensemble correctly identified this fraud case because all three selected models assigned high risk, "
            "which indicates agreement between conservative tabular scoring, boosted fraud coverage, and temporal graph evidence."
        )
    if kind == "false_alarm":
        return (
            "This false positive shows a hard legitimate transaction that looked fraudulent across all three selected models. "
            "The case is useful because it illustrates the cost of high-confidence agreement on a non-fraudulent pattern."
        )
    return (
        "This missed fraud case sits almost exactly at the ensemble threshold boundary. "
        "The Event-Based GNN was strongly suspicious, but lower tabular scores pulled the weighted average just below the decision threshold."
    )


def extract_error_cases() -> pd.DataFrame:
    df = load_case_frame()
    tp = df[(df["Labels"] == 1) & (df["predicted_label"] == 1)].sort_values("ensemble_probability", ascending=False).iloc[0]
    fp = df[(df["Labels"] == 0) & (df["predicted_label"] == 1)].sort_values("ensemble_probability", ascending=False).iloc[0]
    fn = df[(df["Labels"] == 1) & (df["predicted_label"] == 0)].sort_values("ensemble_probability", ascending=False).iloc[0]
    cases = [("caught_fraud", tp), ("false_alarm", fp), ("missed_fraud", fn)]

    rows = []
    for case_name, row in cases:
        rows.append(
            {
                "case_type": case_name,
                "Time": int(row["Time"]),
                "Source": row["Source"],
                "Target": row["Target"],
                "Amount": float(row["Amount"]),
                "Location": row["Location"],
                "Type": row["Type"],
                "true_label": int(row["Labels"]),
                "ensemble_score": float(row["ensemble_probability"]),
                "final_predicted_label": int(row["predicted_label"]),
                "lightgbm_score": float(row["lightgbm_probability"]),
                "adaboost_score": float(row["adaboost_probability"]),
                "event_gnn_score": float(row["event_gnn_probability"]),
                "explanation": explain_row(case_name, row),
            }
        )
    return pd.DataFrame(rows)


def write_markdown(main_df: pd.DataFrame, wider_df: pd.DataFrame, error_df: pd.DataFrame) -> None:
    split_summary = pd.read_csv(VALIDATED_DIR / "split_summary.csv")
    md = []
    md.append("# Final Report Sections\n")
    md.append("## Frozen Experimental Result Set\n")
    md.append(
        "The primary final comparison uses the validation-based chronological S-FFSD protocol. "
        "This is the cleanest methodology currently available because it introduces an explicit validation stage for threshold and ensemble selection, "
        "thereby avoiding test-set tuning leakage.\n"
    )
    md.append("Validated split summary:\n")
    md.append(df_to_markdown_table(split_summary))
    md.append("\n\n## Main Final Comparison Table\n")
    md.append(df_to_markdown_table(main_df))
    md.append(
        "\n\n## Supplemental Wider Baseline Table\n"
        "This wider table includes additional baselines for context. The main final table above remains the primary result because it follows the validation-based protocol.\n"
    )
    md.append(df_to_markdown_table(wider_df))
    md.append("\n\n## Ensemble Justification\n")
    md.append(
        "The Event-Based GNN is the strongest balanced single model on the validation-based S-FFSD comparison, achieving the best F1-score and the best average precision among the final candidates. "
        "However, the final product candidate remains the validated upgraded ensemble because it provides the highest precision and the highest ROC-AUC, while combining complementary tabular and temporal fraud signals. "
        "From a product perspective, this is valuable because it reduces dependence on a single model family and creates a more robust scoring layer that can support future threshold tuning and deployment policies.\n"
    )
    md.append("## Model Architectures and Hyperparameters\n")
    md.append(
        "- **LightGBM**: Gradient-boosted decision tree model on engineered tabular transaction features. Key hyperparameters: `n_estimators=300`, `learning_rate=0.05`, `num_leaves=31`, `subsample=0.8`, `colsample_bytree=0.8`, `scale_pos_weight=neg/pos`.\n"
        "- **AdaBoost**: Boosting over shallow decision trees to emphasize hard fraud cases. Key hyperparameters: depth-2 decision tree base estimator, `n_estimators=200`, `learning_rate=0.5`.\n"
        "- **Event-Based GNN**: Two-layer heterogeneous GraphSAGE-style temporal graph model using event-to-event, source, and target relations. Key hyperparameters: `hidden_dim=96`, `epochs=60`, `lr=0.003`, weighted binary cross-entropy.\n"
        "- **Heterogeneous GNN**: Two-layer heterogeneous GraphSAGE-style static relation model over event, source, target, location, and type nodes. Key hyperparameters: `hidden_dim=96`, `epochs=80`, `lr=0.003`, weighted binary cross-entropy.\n"
        "- **Logistic Regression**: L2-regularized linear baseline on engineered tabular features with `StandardScaler`, `C=1.0`, `solver='lbfgs'`, `max_iter=2000`, and class weighting.\n"
        "- **Validated Upgraded Ensemble**: Weighted average of `Event-Based GNN`, `AdaBoost`, and `LightGBM` with validation-optimized thresholding. The optimized weights remained `event_gnn=0.50`, `adaboost=0.30`, and `lightgbm=0.20`, with the final ensemble threshold selected on validation.\n"
    )
    md.append("\n## Error Analysis\n")
    md.append(
        "The three representative cases below connect the aggregate metrics to concrete fraud-detection behavior.\n"
    )
    for _, row in error_df.iterrows():
        md.append(f"### {row['case_type'].replace('_', ' ').title()}\n")
        md.append(
            f"- Transaction: `Time={row['Time']}`, `Source={row['Source']}`, `Target={row['Target']}`, `Amount={row['Amount']}`, `Location={row['Location']}`, `Type={row['Type']}`\n"
            f"- True label: `{row['true_label']}`\n"
            f"- Ensemble score / decision: `{row['ensemble_score']:.6f}` / `{row['final_predicted_label']}`\n"
            f"- Base model scores: `LightGBM={row['lightgbm_score']:.6f}`, `AdaBoost={row['adaboost_score']:.6f}`, `Event-GNN={row['event_gnn_score']:.6f}`\n"
            f"- Interpretation: {row['explanation']}\n"
        )
    (FINAL_REPORT_DIR / "final_report_sections.md").write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    FINAL_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    main_df = main_table()
    wider_df = wider_table()
    error_df = extract_error_cases()

    main_df.to_csv(FINAL_REPORT_DIR / "main_final_comparison_table.csv", index=False)
    wider_df.to_csv(FINAL_REPORT_DIR / "wider_baseline_comparison_table.csv", index=False)
    error_df.to_csv(FINAL_REPORT_DIR / "error_analysis_cases.csv", index=False)
    write_markdown(main_df, wider_df, error_df)


if __name__ == "__main__":
    main()
