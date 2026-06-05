ALTER TABLE case_score_runs
ADD COLUMN mlflow_run_id VARCHAR(255) NULL;

ALTER TABLE case_score_runs
ADD COLUMN model_artifact_uri VARCHAR(1024) NULL;

ALTER TABLE case_score_runs
ADD COLUMN model_metadata JSON NULL;
