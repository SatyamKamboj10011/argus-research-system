export interface SourceRow {
  url: string;
  title: string;
  snippet?: string;
  score?: number;
  domain?: string;
}

export interface PageRow {
  url: string;
  /** The URL that was requested; differs from `url` when a redirect was followed. */
  source_url?: string;
  title?: string;
  chars?: number;
  error?: string | null;
}

export interface Scores {
  overall?: number;
  categories?: Record<string, number>;
  verdict?: string;
  recommendation?: "APPROVE" | "NEEDS REVISION" | "REJECT";
}

export interface ResearchResult {
  run_id?: string;
  topic?: string;
  report: string;
  critic: string;
  factcheck: string;
  credibility: string;
  followup: string;
  followup_questions: string[];
  scores: Scores;
  fact_check_summary: { score?: number; verdict?: string };
  sources: SourceRow[];
  pages: PageRow[];
  search_results: string;
  scraped_content: string;
  timings_ms: Record<string, number>;
  total_ms: number;
  cached?: boolean;
}

export interface ModelRow {
  id: string;
  label: string;
  provider: string;
  description: string;
  context_window: number;
  is_local: boolean;
  recommended: boolean;
  ready: boolean;
  key_env_var: string | null;
}

export type StageStatus = "pending" | "running" | "done" | "failed";

export interface StageState {
  id: string;
  status: StageStatus;
  offsetMs: number | null;
  durationMs: number | null;
  error?: string;
}

export type RunStatus = "idle" | "connecting" | "running" | "done" | "error";

export interface RunState {
  status: RunStatus;
  runId: string | null;
  topic: string;
  modelLabel: string;
  startedAt: number | null;
  stages: Record<string, StageState>;
  report: string;
  result: ResearchResult | null;
  sources: SourceRow[];
  pages: PageRow[];
  error: string;
  notices: string[];
  cached: boolean;
}

export interface PipelineEvent {
  event: string;
  data?: Record<string, unknown>;
}
