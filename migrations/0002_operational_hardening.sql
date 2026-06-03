CREATE TABLE fraud_feedback (
    id BIGSERIAL PRIMARY KEY,
    scored_case_id BIGINT NOT NULL REFERENCES scored_cases(id),
    reviewer_user_id BIGINT NOT NULL REFERENCES users(id),
    confirmed_label VARCHAR(32) NOT NULL,
    feedback_timestamp TIMESTAMPTZ NOT NULL,
    note TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_fraud_feedback_scored_case_id ON fraud_feedback(scored_case_id);

CREATE TABLE monitoring_events (
    id BIGSERIAL PRIMARY KEY,
    scored_case_id BIGINT NOT NULL REFERENCES scored_cases(id),
    score_run_id BIGINT NULL REFERENCES case_score_runs(id),
    actor_user_id BIGINT NULL REFERENCES users(id),
    transaction_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    latency_ms DOUBLE PRECISION NOT NULL,
    decision VARCHAR(32) NOT NULL,
    final_risk_score DOUBLE PRECISION NOT NULL,
    history_available BOOLEAN NOT NULL,
    graph_context_available BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_monitoring_events_scored_case_id ON monitoring_events(scored_case_id);
CREATE INDEX ix_monitoring_events_score_run_id ON monitoring_events(score_run_id);
CREATE INDEX ix_monitoring_events_transaction_id ON monitoring_events(transaction_id);
CREATE INDEX ix_monitoring_events_event_type ON monitoring_events(event_type);
