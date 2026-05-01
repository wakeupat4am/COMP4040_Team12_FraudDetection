"""Data ingestion and entity-resolution pipeline."""


def describe_ingestion_scope() -> str:
    """Return the expected inputs for the ingestion layer."""
    return (
        "Load orders, payments, refunds, clickstream, support text, and graph "
        "sources; then align them to order_id, user_id, session_id, and ticket_id."
    )
