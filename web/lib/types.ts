export type DecisionValue = "allow" | "review" | "block";
export type RoleValue = "analyst" | "manager_admin";
export type ReviewStatusValue = "pending" | "reviewed";
export type ConfirmedLabelValue = "fraud" | "legitimate";
export type ConfidenceValue = "low" | "medium" | "high";

export interface AuthSession {
  accessToken: string;
  role: RoleValue;
  tokenType: string;
  username: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: RoleValue;
}

export interface OverviewModelScores {
  LightGBM: number;
  AdaBoost: number;
  Event_GNN: number;
}

export interface ExplanationSummary {
  main_risk_source: string;
  tabular_signal: "high" | "medium" | "low";
  graph_signal: "high" | "low";
  reason: string;
}

export interface PipelineOutputContract {
  transaction_id: string;
  pipeline_profile: string;
  final_risk_score: number;
  fraud_score: number;
  threshold: number;
  risk_bucket: string;
  decision: DecisionValue;
  model_scores: Record<string, number>;
  model_scores_overview: OverviewModelScores;
  required_state_status: Record<string, boolean>;
  routing_metadata: Record<string, unknown>;
  explanation_summary: ExplanationSummary;
  explanations: Record<string, unknown>;
}

export interface CaseQueueItem {
  transaction_id: string;
  final_risk_score: number;
  risk_bucket: string;
  decision: DecisionValue;
  review_status: ReviewStatusValue;
  last_scored_at: string;
  created_at: string;
  updated_at: string;
  latest_analyst_decision: DecisionValue | null;
  latest_note: string | null;
}

export interface AuditEntry {
  action: string;
  details: Record<string, unknown>;
  created_at: string;
  actor_username: string | null;
}

export interface ReviewEntry {
  analyst_decision: DecisionValue;
  note: string;
  created_at: string;
  analyst_username: string | null;
}

export interface FeedbackEntry {
  confirmed_label: ConfirmedLabelValue;
  feedback_timestamp: string;
  note: string | null;
  reviewer_username: string | null;
}

export interface GeminiAnalysisResponse {
  recommended_decision: DecisionValue;
  confidence: ConfidenceValue;
  summary: string;
  key_factors: string[];
  risk_flags: string[];
  follow_up_actions: string[];
  model: string;
  analyzed_at: string;
  source_score_run_id: number;
}

export interface CaseDetailResponse extends CaseQueueItem {
  original_request_payload: Record<string, unknown>;
  latest_output: PipelineOutputContract;
  explanation_payload: Record<string, unknown>;
  routing_metadata: Record<string, unknown>;
  latest_gemini_analysis: GeminiAnalysisResponse | null;
  latest_score_run_id: number | null;
  review_history: ReviewEntry[];
  feedback_history: FeedbackEntry[];
  audit_trail: AuditEntry[];
}

export interface CaseListResponse {
  items: CaseQueueItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface MetricsSummaryResponse {
  total_cases: number;
  average_final_risk_score: number;
  risk_bucket_counts: Record<string, number>;
  decision_counts: Record<string, number>;
  review_status_counts: Record<string, number>;
  pending_review_cases: number;
}

export interface MonitoringSummaryResponse {
  total_events: number;
  average_latency_ms: number;
  event_type_counts: Record<string, number>;
  average_latency_by_event_type: Record<string, number>;
  latest_event_at: string | null;
}

export interface ScoreRequestPayload {
  transaction_id: string;
  transaction_timestamp: string;
  sender_id: string;
  receiver_id: string;
  amount: number;
  transaction_location: string;
  transaction_type: string;
  currency?: string;
  channel?: string;
  raw_attributes?: Record<string, unknown>;
}

export interface AnalystDecisionPayload {
  analyst_decision: DecisionValue;
  note: string;
}

export interface FeedbackPayload {
  confirmed_label: ConfirmedLabelValue;
  feedback_timestamp?: string;
  note?: string;
}

export interface CaseListFilters {
  risk_bucket?: string;
  decision?: string;
  review_status?: string;
  created_from?: string;
  created_to?: string;
  page?: number;
  page_size?: number;
}
