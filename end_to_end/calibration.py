from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.isotonic import IsotonicRegression


def fit_isotonic_calibrator(scores: pd.Series, labels: pd.Series) -> IsotonicRegression:
    model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    model.fit(scores.to_numpy(), labels.to_numpy())
    return model


def save_calibrator(model: IsotonicRegression, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)


def load_calibrator(path: Path) -> IsotonicRegression:
    return joblib.load(path)


def apply_calibrator(model: IsotonicRegression, score: float) -> float:
    return float(model.predict([score])[0])
