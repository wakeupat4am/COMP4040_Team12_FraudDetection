CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(32) NOT NULL DEFAULT 'analyst',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scored_events (
    id INTEGER PRIMARY KEY,
    event_id VARCHAR(255) NOT NULL UNIQUE,
    dataset_family VARCHAR(32) NOT NULL,
    final_risk_score DOUBLE PRECISION NOT NULL,
    risk_bucket VARCHAR(32) NOT NULL,
    decision VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'scored',
    current_analyst_decision VARCHAR(32),
    analyst_note TEXT,
    request_payload JSON NOT NULL,
    score_payload JSON NOT NULL,
    explanation_payload JSON NOT NULL,
    scored_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decision_updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_scored_events_event_id ON scored_events (event_id);
CREATE INDEX IF NOT EXISTS ix_scored_events_dataset_family ON scored_events (dataset_family);
CREATE INDEX IF NOT EXISTS ix_scored_events_risk_bucket ON scored_events (risk_bucket);
CREATE INDEX IF NOT EXISTS ix_scored_events_decision ON scored_events (decision);
CREATE INDEX IF NOT EXISTS ix_scored_events_status ON scored_events (status);

CREATE TABLE IF NOT EXISTS analyst_reviews (
    id INTEGER PRIMARY KEY,
    event_id VARCHAR(255) NOT NULL REFERENCES scored_events(event_id),
    analyst_decision VARCHAR(32) NOT NULL,
    note TEXT NOT NULL,
    user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_analyst_reviews_event_id ON analyst_reviews (event_id);
CREATE INDEX IF NOT EXISTS ix_analyst_reviews_created_at ON analyst_reviews (created_at);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY,
    event_id VARCHAR(255) REFERENCES scored_events(event_id),
    action VARCHAR(64) NOT NULL,
    actor VARCHAR(255) NOT NULL DEFAULT 'system',
    payload JSON NOT NULL,
    user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_audit_logs_event_id ON audit_logs (event_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at);
