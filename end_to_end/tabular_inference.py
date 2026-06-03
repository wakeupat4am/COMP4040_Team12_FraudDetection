from __future__ import annotations

import pandas as pd

from .calibration import apply_calibrator
from .model_loader import load_adaboost_model, load_calibrators, load_lightgbm_model, load_runtime_metadata


class TabularInferenceEngine:
    def __init__(self) -> None:
        self.lightgbm_model = load_lightgbm_model()
        self.adaboost_model = load_adaboost_model()
        self.calibrators = load_calibrators()
        self.metadata = load_runtime_metadata()
        self.categorical_columns = self.metadata["categorical_columns"]
        self.lightgbm_features = self.metadata["lightgbm_features"]
        self.adaboost_features = self.metadata["adaboost_features"]

    def score(self, features: dict[str, float | int | str]) -> dict[str, float]:
        frame = pd.DataFrame([features]).copy()
        lightgbm_input = frame[self.lightgbm_features].copy()
        for col in self.categorical_columns:
            lightgbm_input[col] = lightgbm_input[col].astype("category")
        adaboost_input = frame[self.adaboost_features].copy()

        raw_lightgbm = float(self.lightgbm_model.predict_proba(lightgbm_input)[:, 1][0])
        raw_adaboost = float(self.adaboost_model.predict_proba(adaboost_input)[:, 1][0])
        return {
            "lightgbm_raw": raw_lightgbm,
            "adaboost_raw": raw_adaboost,
            "lightgbm": apply_calibrator(self.calibrators["lightgbm"], raw_lightgbm),
            "adaboost": apply_calibrator(self.calibrators["adaboost"], raw_adaboost),
        }
