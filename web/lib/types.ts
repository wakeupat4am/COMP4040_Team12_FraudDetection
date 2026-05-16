export type RiskBucket = "low" | "medium" | "high" | "critical";
export type Decision = "allow" | "review" | "block";
export type CaseStatus = "scored" | "reviewed";

export interface QueueItem {
  event_id: string;
  dataset_family: "ssfd" | "paysim";
  final_risk_score: number;
  risk_bucket: RiskBucket;
  decision: Decision;
  status: CaseStatus;
  scored_at: string;
  current_analyst_decision: Decision | null;
  decision_updated_at: string | null;
}

export interface QueueResponse {
  items: QueueItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface Contributor {
  feature: string;
  direction: "increase" | "decrease";
  magnitude: number;
  summary: string;
}

export interface EvidencePanel {
  panel: string;
  title: string;
  items: string[];
}

export interface CaseDetail {
  event_id: string;
  dataset_family: "ssfd" | "paysim";
  final_risk_score: number;
  risk_bucket: RiskBucket;
  decision: Decision;
  model_scores: {
    event_gnn: number;
    adaboost: number;
    lightgbm: number;
    hetero_gnn_shadow: number | null;
  };
  required_state_status: {
    history_available: boolean;
    graph_context_available: boolean;
  };
  routing_metadata: {
    selected_ensemble: string;
    base_models: string[];
  };
  explanation_stub: {
    summary: string;
    top_contributors: Contributor[];
    state_availability: {
      history_available: boolean;
      graph_context_available: boolean;
      history_summary: string;
      graph_summary: string;
    };
    evidence_panels: EvidencePanel[];
  };
  scored_at: string;
  status: CaseStatus;
  current_analyst_decision: Decision | null;
  analyst_note: string | null;
  decision_updated_at: string | null;
}

export interface MetricsSummary {
  total_cases: number;
  by_risk_bucket: Record<string, number>;
  by_decision: Record<string, number>;
  reviewed_cases: number;
}
