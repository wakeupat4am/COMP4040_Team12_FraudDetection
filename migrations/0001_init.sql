CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(128) NOT NULL UNIQUE,
    password_hash VARCHAR(512) NOT NULL,
    role VARCHAR(32) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    last_login_at TIMESTAMPTZ NULL
);

CREATE TABLE scored_cases (
    id BIGSERIAL PRIMARY KEY,
    transaction_id VARCHAR(255) NOT NULL UNIQUE,
    original_request_payload JSONB NOT NULL,
    current_output_payload JSONB NOT NULL,
    explanation_payload JSONB NOT NULL,
    routing_metadata JSONB NOT NULL,
    pipeline_profile VARCHAR(128) NOT NULL,
    final_risk_score DOUBLE PRECISION NOT NULL,
    risk_bucket VARCHAR(32) NOT NULL,
    decision VARCHAR(32) NOT NULL,
    review_status VARCHAR(32) NOT NULL,
    latest_analyst_decision VARCHAR(32) NULL,
    latest_note TEXT NULL,
    latest_score_run_id BIGINT NULL,
    last_scored_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE case_score_runs (
    id BIGSERIAL PRIMARY KEY,
    scored_case_id BIGINT NOT NULL REFERENCES scored_cases(id),
    triggered_by_user_id BIGINT NULL REFERENCES users(id),
    run_type VARCHAR(32) NOT NULL,
    request_payload JSONB NOT NULL,
    output_payload JSONB NOT NULL,
    explanation_payload JSONB NOT NULL,
    routing_metadata JSONB NOT NULL,
    final_risk_score DOUBLE PRECISION NOT NULL,
    risk_bucket VARCHAR(32) NOT NULL,
    decision VARCHAR(32) NOT NULL,
    scored_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

ALTER TABLE scored_cases
ADD CONSTRAINT fk_scored_cases_latest_score_run_id
FOREIGN KEY (latest_score_run_id) REFERENCES case_score_runs(id);

CREATE TABLE analyst_reviews (
    id BIGSERIAL PRIMARY KEY,
    scored_case_id BIGINT NOT NULL REFERENCES scored_cases(id),
    analyst_user_id BIGINT NOT NULL REFERENCES users(id),
    analyst_decision VARCHAR(32) NOT NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_user_id BIGINT NULL REFERENCES users(id),
    transaction_id VARCHAR(255) NULL,
    action VARCHAR(64) NOT NULL,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_case_score_runs_scored_case_id ON case_score_runs(scored_case_id);
CREATE INDEX ix_analyst_reviews_scored_case_id ON analyst_reviews(scored_case_id);
CREATE INDEX ix_audit_logs_transaction_id ON audit_logs(transaction_id);
CREATE INDEX ix_audit_logs_action ON audit_logs(action);
