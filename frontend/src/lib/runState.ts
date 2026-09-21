/**
 * Reduces the pipeline's event stream into render state.
 *
 * Kept as a pure function so the timeline can be tested against a recorded event
 * sequence. Every timing shown in the UI comes from the server's own timestamps;
 * nothing here invents progress.
 */
import type { PageRow, PipelineEvent, RunState, SourceRow, StageState } from "./types";

export const STAGE_ORDER = [
  "search",
  "read",
  "write",
  "critic",
  "factcheck",
  "credibility",
  "followup",
] as const;

export const STAGE_LABELS: Record<string, string> = {
  search: "Search the web",
  read: "Read the pages",
  write: "Write the report",
  critic: "Grade the report",
  factcheck: "Check the claims",
  credibility: "Weigh the sources",
  followup: "Ask what is next",
};

export const STAGE_DETAIL: Record<string, string> = {
  search: "A ReAct agent queries Tavily and refines its own query",
  read: "Top sources are fetched in parallel and stripped to text",
  write: "Sources become a structured report, streamed as written",
  critic: "Scored across six dimensions against a strict rubric",
  factcheck: "Each claim is re-checked against the source material",
  credibility: "Every source weighed for authority, currency and bias",
  followup: "The report's own gaps become the next five questions",
};

export const initialState: RunState = {
  status: "idle",
  runId: null,
  topic: "",
  modelLabel: "",
  startedAt: null,
  stages: {},
  report: "",
  result: null,
  sources: [],
  pages: [],
  error: "",
  notices: [],
  cached: false,
};

function blankStages(): Record<string, StageState> {
  return Object.fromEntries(
    STAGE_ORDER.map((id) => [id, { id, status: "pending", offsetMs: null, durationMs: null }])
  ) as Record<string, StageState>;
}

export function startState(topic: string): RunState {
  return { ...initialState, status: "connecting", topic, stages: blankStages() };
}

/** Seconds-since-epoch from the server, converted to ms since this run began. */
function offsetOf(state: RunState, ts: unknown): number | null {
  if (!state.startedAt || typeof ts !== "number") return null;
  return Math.max(0, Math.round((ts - state.startedAt) * 1000));
}

export function reduce(state: RunState, { event, data = {} }: PipelineEvent): RunState {
  const stage = data.stage as string | undefined;

  switch (event) {
    case "open":
      return { ...state, status: "connecting", modelLabel: (data.model_label as string) || "" };

    case "run_started":
      return {
        ...state,
        status: "running",
        runId: (data.run_id as string) ?? null,
        startedAt: (data.ts as number) ?? null,
        cached: Boolean(data.cached),
        stages: blankStages(),
        report: "",
        error: "",
      };

    case "stage_started":
      return withStage(state, stage, (s) => ({
        ...s,
        status: "running",
        offsetMs: offsetOf(state, data.ts),
      }));

    case "stage_completed": {
      const duration = (data.duration_ms as number) ?? null;
      const endOffset = offsetOf(state, data.ts);
      return withStage(applyStageData(state, data), stage, (s) => ({
        ...s,
        status: "done",
        durationMs: duration,
        offsetMs:
          s.offsetMs ?? (endOffset !== null ? Math.max(0, endOffset - (duration ?? 0)) : null),
      }));
    }

    case "stage_failed":
      return withStage(state, stage, (s) => ({
        ...s,
        status: "failed",
        durationMs: (data.duration_ms as number) ?? s.durationMs,
        error: (data.error as string) || "This stage did not complete.",
      }));

    case "stage_warning":
      return { ...state, notices: [...state.notices, data.message as string].filter(Boolean) };

    case "token":
      return { ...state, report: state.report + ((data.text as string) || "") };

    case "run_completed": {
      const result = data.result as RunState["result"];
      if (!result) return state;
      return {
        ...state,
        status: "done",
        result,
        cached: Boolean(result.cached),
        report: result.report || state.report,
        sources: result.sources || state.sources,
        pages: result.pages || state.pages,
      };
    }

    case "run_failed":
      return {
        ...state,
        status: "error",
        error: (data.error as string) || "The run did not complete.",
      };

    default:
      return state;
  }
}

function withStage(
  state: RunState,
  id: string | undefined,
  update: (stage: StageState) => StageState
): RunState {
  if (!id || !state.stages[id]) return state;
  return { ...state, stages: { ...state.stages, [id]: update(state.stages[id]) } };
}

/** Stages carry payloads worth showing before the run finishes. */
function applyStageData(state: RunState, data: Record<string, unknown>): RunState {
  if (data.stage === "search" && Array.isArray(data.sources)) {
    return { ...state, sources: data.sources as SourceRow[] };
  }
  if (data.stage === "read" && Array.isArray(data.pages)) {
    return { ...state, pages: data.pages as PageRow[] };
  }
  return state;
}

/** Total span the Gantt must cover, in ms. */
export function timelineSpan(stages: Record<string, StageState>, nowMs = 0): number {
  const ends = Object.values(stages)
    .filter((s) => s.offsetMs !== null)
    .map((s) => s.offsetMs! + (s.durationMs ?? Math.max(0, nowMs - s.offsetMs!)));
  return Math.max(1000, ...ends);
}
