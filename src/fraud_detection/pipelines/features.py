"""Feature engineering pipeline."""


def describe_feature_scope() -> str:
    """Return the expected responsibility of the feature layer."""
    return (
        "Build leakage-safe tabular, session, text, and graph-derived features "
        "using only information available at decision time."
    )
