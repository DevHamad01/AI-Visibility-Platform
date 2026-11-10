export type RunStatus = 'queued' | 'running' | 'succeeded' | 'partial' | 'failed';
export type StageStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'skipped';
export type RecommendationStatus = 'todo' | 'in_progress' | 'done' | 'dismissed';
export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}
export interface BrandInput {
  name: string;
  domain: string;
  description?: string | null;
  industry?: string | null;
  location_code?: number | null;
  language_code?: string | null;
}
export interface Brand extends BrandInput {
  id: string;
  created_at: string;
  updated_at: string;
}
export interface CompetitorInput {
  name: string;
  domain: string;
}
export interface Competitor extends CompetitorInput {
  id: string;
  brand_id: string;
  created_at: string;
}
export interface Stage {
  stage: string;
  status: StageStatus;
  attempts: number;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  error_type: string | null;
  error_message: string | null;
  output_summary: Record<string, unknown> | null;
}
export interface RunSummary {
  id: string;
  brand_id: string;
  status: RunStatus;
  trigger: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  llm_provider: string | null;
  llm_model: string | null;
  trace_id: string | null;
  progress: Record<string, number>;
  metrics: Record<string, number>;
  error_summary: string | null;
  dataforseo_cost_usd: number;
  idempotency_key: string | null;
}
export interface Run extends RunSummary {
  stages: Stage[];
}
export interface RunEvent {
  status?: RunStatus;
  progress?: Record<string, number>;
  stages?: Pick<Stage, 'stage' | 'status' | 'attempts' | 'duration_ms' | 'error_type'>[];
  error?: string;
  warning?: string;
}
export interface Observation {
  channel: string;
  brand_visible: boolean;
  brand_position: number | null;
  competitors_visible: string[];
  cited_urls: string[];
}
export interface VisibilityQuery {
  id: string;
  text: string;
  source: string;
  intent: string | null;
  search_volume: number | null;
  observations: Observation[];
}
export interface VisibilityMatrix {
  queries: VisibilityQuery[];
}
export interface Opportunity {
  id: string;
  query_id: string;
  query_text: string;
  score: number;
  rank: number;
  components: Record<string, unknown>;
  explanation: string | null;
}
export interface Recommendation {
  id: string;
  opportunity_id: string;
  title: string;
  content_type: string;
  target_query: string | null;
  outline: string[] | null;
  rationale: string | null;
  priority: string | null;
  effort: string | null;
  status: RecommendationStatus;
}
export interface BrandOverview {
  brand_id: string;
  brand_name: string;
  latest_run_id: string | null;
  latest_run_status: RunStatus | null;
  latest_run_finished_at: string | null;
  top_score: number | null;
  opportunity_count: number;
}
export interface Overview {
  brands: BrandOverview[];
}
export interface OpportunityDelta {
  query_text: string;
  base_score: number | null;
  target_score: number | null;
  delta: number | null;
  change: 'improved' | 'declined' | 'new' | 'dropped' | 'unchanged';
}
export interface Comparison {
  base_run_id: string;
  target_run_id: string;
  deltas: OpportunityDelta[];
}
export interface Problem {
  title?: string;
  detail?: string;
  trace_id?: string;
  errors?: { loc?: (string | number)[]; msg?: string }[];
}
