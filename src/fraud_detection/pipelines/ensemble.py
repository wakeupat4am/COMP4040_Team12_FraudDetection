"""Score fusion and final decisioning."""


def describe_ensemble_scope() -> str:
    """Return the planned ensemble module purpose."""
    return (
        "Combine anomaly, graph, and text scores into a calibrated final risk "
        "score and risk bucket."
    )
