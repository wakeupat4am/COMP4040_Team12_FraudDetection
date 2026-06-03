from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIGURES_DIR = PROJECT_ROOT / "figures"
FINAL_REPORT_DIR = PROJECT_ROOT / "Final_Report"
MODELS_DIR = PROJECT_ROOT / "models"
MPLCONFIGDIR = PROJECT_ROOT / "end_to_end" / "artifacts" / "mplconfig"
MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIGDIR))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def ensure_figures_dir() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def save_ssfd_final_comparison() -> None:
    df = pd.read_csv(FINAL_REPORT_DIR / "main_final_comparison_table.csv")
    metric_columns = ["accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"]
    rename_map = {
        "accuracy": "Accuracy",
        "precision": "Precision",
        "recall": "Recall",
        "f1": "F1",
        "roc_auc": "ROC-AUC",
        "average_precision": "Avg Precision",
    }

    fig, ax = plt.subplots(figsize=(13.5, 6.5))
    x = np.arange(len(metric_columns))
    width = 0.18
    colors = ["#3B82F6", "#F97316", "#10B981", "#111827"]

    for idx, (_, row) in enumerate(df.iterrows()):
        values = [row[col] for col in metric_columns]
        ax.bar(x + (idx - 1.5) * width, values, width=width, label=row["model"], color=colors[idx])

    ax.set_xticks(x)
    ax.set_xticklabels([rename_map[col] for col in metric_columns], rotation=15)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Score")
    ax.set_title("S-FFSD Final Model Comparison")
    ax.legend(frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5))
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout(rect=[0, 0, 0.83, 1])
    fig.savefig(FIGURES_DIR / "ssfd_final_model_comparison.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_paysim_strict_comparison() -> None:
    df = pd.read_csv(MODELS_DIR / "paysim_strict_comparison" / "comparison_metrics.csv")
    metric_columns = ["accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"]
    rename_map = {
        "accuracy": "Accuracy",
        "precision": "Precision",
        "recall": "Recall",
        "f1": "F1",
        "roc_auc": "ROC-AUC",
        "average_precision": "Avg Precision",
    }

    fig, ax = plt.subplots(figsize=(13.5, 6.5))
    x = np.arange(len(metric_columns))
    width = 0.18
    colors = ["#2563EB", "#EA580C", "#059669", "#7C3AED"]

    for idx, (_, row) in enumerate(df.iterrows()):
        values = [row[col] for col in metric_columns]
        ax.bar(x + (idx - 1.5) * width, values, width=width, label=row["model"], color=colors[idx])

    ax.set_xticks(x)
    ax.set_xticklabels([rename_map[col] for col in metric_columns], rotation=15)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Score")
    ax.set_title("PaySim Strict-Split Model Comparison")
    ax.legend(frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5))
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout(rect=[0, 0, 0.83, 1])
    fig.savefig(FIGURES_DIR / "paysim_strict_model_comparison.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_paysim_shortcut_signal() -> None:
    diagnostics = json.loads((MODELS_DIR / "paysim_leakage_diagnostics.json").read_text(encoding="utf-8"))
    single = diagnostics["single_feature_separability"]
    df = (
        pd.DataFrame(
            [
                {
                    "feature": feature,
                    "roc_auc": values["roc_auc"],
                    "average_precision": values["average_precision"],
                }
                for feature, values in single.items()
            ]
        )
        .sort_values("roc_auc", ascending=False)
        .reset_index(drop=True)
    )

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.5))
    axes[0].barh(df["feature"], df["roc_auc"], color="#DC2626")
    axes[0].invert_yaxis()
    axes[0].set_title("PaySim Single-Feature ROC-AUC")
    axes[0].set_xlim(0, 1.0)
    axes[0].grid(axis="x", alpha=0.2)

    axes[1].barh(df["feature"], df["average_precision"], color="#F59E0B")
    axes[1].invert_yaxis()
    axes[1].set_title("PaySim Single-Feature Average Precision")
    axes[1].set_xlim(0, 1.0)
    axes[1].grid(axis="x", alpha=0.2)

    fig.suptitle("PaySim Shortcut-Signal Diagnostics", y=1.02)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(FIGURES_DIR / "paysim_shortcut_signal.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def _load_prediction_frame(model_name: str, path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    key_columns = ["Time", "Source", "Target", "Amount", "Location", "Type", "Labels"]
    out = df[key_columns + ["predicted_probability"]].copy()
    out = out.rename(columns={"predicted_probability": f"{model_name}_probability"})
    return out


def save_ssfd_correlation_heatmap() -> None:
    prediction_files = {
        "LightGBM": MODELS_DIR / "ssfd_lightgbm" / "ssfd_lightgbm_test_predictions.csv",
        "AdaBoost": MODELS_DIR / "ssfd_adaboost" / "ssfd_adaboost_test_predictions.csv",
        "Event-GNN": MODELS_DIR / "ssfd_event_gnn" / "ssfd_event_gnn_test_predictions.csv",
    }

    merged: pd.DataFrame | None = None
    for model_name, path in prediction_files.items():
        frame = _load_prediction_frame(model_name.lower().replace("-", "_"), path)
        if merged is None:
            merged = frame
        else:
            merged = merged.merge(frame, on=["Time", "Source", "Target", "Amount", "Location", "Type", "Labels"], how="inner")

    if merged is None:
        raise RuntimeError("Failed to merge prediction frames for correlation figure.")

    columns = ["lightgbm_probability", "adaboost_probability", "event_gnn_probability"]
    labels = ["LightGBM", "AdaBoost", "Event-GNN"]
    pearson = merged[columns].corr(method="pearson").to_numpy()
    spearman = merged[columns].corr(method="spearman").to_numpy()

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.5))
    for ax, matrix, title in zip(axes, [pearson, spearman], ["Pearson Score Correlation", "Spearman Score Correlation"], strict=True):
        im = ax.imshow(matrix, vmin=0, vmax=1, cmap="Blues")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=20)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels)
        ax.set_title(title)
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                ax.text(j, i, f"{matrix[i, j]:.3f}", ha="center", va="center", color="black")
    cbar = fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.8, location="right", pad=0.04)
    cbar.ax.set_ylabel("Correlation", rotation=270, labelpad=14)
    fig.tight_layout(rect=[0, 0, 0.94, 1])
    fig.savefig(FIGURES_DIR / "ssfd_selected_model_correlation.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_readme() -> None:
    content = """# Figures

Generated report-ready figures:

- `ssfd_final_model_comparison.png`: main final S-FFSD comparison chart
- `paysim_strict_model_comparison.png`: stricter PaySim comparison chart
- `paysim_shortcut_signal.png`: PaySim shortcut-signal evidence from leakage diagnostics
- `ssfd_selected_model_correlation.png`: selected-model correlation heatmap for ensemble motivation
"""
    (FIGURES_DIR / "README.md").write_text(content, encoding="utf-8")


def main() -> None:
    ensure_figures_dir()
    save_ssfd_final_comparison()
    save_paysim_strict_comparison()
    save_paysim_shortcut_signal()
    save_ssfd_correlation_heatmap()
    save_readme()


if __name__ == "__main__":
    main()
