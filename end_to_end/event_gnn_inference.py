from __future__ import annotations

import torch

from models.train_ssfd_four_models import build_event_graph_df

from .calibration import apply_calibrator
from .model_loader import load_calibrators, load_event_gnn_model


class EventGNNInferenceEngine:
    def __init__(self) -> None:
        self.calibrators = load_calibrators()
        self.model, self.device = load_event_gnn_model()

    def score(self, context_frame):
        data, graph_df = build_event_graph_df(context_frame.copy())
        data = data.to(self.device)
        with torch.no_grad():
            scores = torch.sigmoid(self.model(data.x_dict, data.edge_index_dict)).cpu().numpy()
        test_mask = data["event"].test_mask.cpu().numpy()
        raw_score = float(scores[test_mask][0])
        return {
            "event_gnn_raw": raw_score,
            "event_gnn": apply_calibrator(self.calibrators["event_gnn"], raw_score),
            "context_graph_rows": len(graph_df),
        }
