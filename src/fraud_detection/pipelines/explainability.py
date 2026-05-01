"""Explainability interfaces for model outputs."""


def describe_explainability_scope() -> str:
    """Return the planned explainability module purpose."""
    return (
        "Expose tabular SHAP signals, graph evidence, and highlighted text "
        "snippets for analyst review."
    )
