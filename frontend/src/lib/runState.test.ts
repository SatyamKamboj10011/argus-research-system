import { expect, test } from "vitest";
import { STAGE_ORDER, initialState, reduce, startState, timelineSpan } from "./runState";
import type { PipelineEvent, RunState } from "./types";

const T0 = 1_760_000_000;

function play(events: PipelineEvent[], from: RunState = startState("rare earths")): RunState {
  return events.reduce<RunState>((state, event) => reduce(state, event), from);
}

test("a run begins with every stage pending", () => {
  const state = play([{ event: "run_started", data: { run_id: "abc", ts: T0 } }]);
  expect(state.status).toBe("running");
  expect(state.runId).toBe("abc");
  expect(STAGE_ORDER.every((id) => state.stages[id].status === "pending")).toBe(true);
});

test("stage offsets are measured from the run's own start time", () => {
  const state = play([
    { event: "run_started", data: { ts: T0 } },
    { event: "stage_started", data: { stage: "search", ts: T0 + 0.5 } },
    { event: "stage_completed", data: { stage: "search", ts: T0 + 3.5, duration_ms: 3000 } },
  ]);
  expect(state.stages.search.offsetMs).toBe(500);
  expect(state.stages.search.durationMs).toBe(3000);
  expect(state.stages.search.status).toBe("done");
});

test("streamed tokens accumulate into the report", () => {
  const state = play([
    { event: "run_started", data: { ts: T0 } },
    { event: "token", data: { text: "## Summary" } },
    { event: "token", data: { text: "\nIt matters." } },
  ]);
  expect(state.report).toBe("## Summary\nIt matters.");
});

test("sources appear as soon as the search stage reports them", () => {
  const state = play([
    { event: "run_started", data: { ts: T0 } },
    {
      event: "stage_completed",
      data: {
        stage: "search",
        duration_ms: 100,
        sources: [{ url: "https://a.com", title: "A" }],
      },
    },
  ]);
  expect(state.sources).toHaveLength(1);
});

test("a failed stage records its reason without failing the run", () => {
  const state = play([
    { event: "run_started", data: { ts: T0 } },
    { event: "stage_failed", data: { stage: "factcheck", error: "Rate limit reached." } },
  ]);
  expect(state.stages.factcheck.status).toBe("failed");
  expect(state.stages.factcheck.error).toBe("Rate limit reached.");
  expect(state.status).toBe("running");
});

test("concurrent review stages overlap on the timeline", () => {
  const state = play([
    { event: "run_started", data: { ts: T0 } },
    { event: "stage_started", data: { stage: "critic", ts: T0 + 10 } },
    { event: "stage_started", data: { stage: "factcheck", ts: T0 + 10 } },
    { event: "stage_completed", data: { stage: "critic", ts: T0 + 31, duration_ms: 21000 } },
    { event: "stage_completed", data: { stage: "factcheck", ts: T0 + 40, duration_ms: 30000 } },
  ]);
  expect(state.stages.critic.offsetMs).toBe(10000);
  expect(state.stages.factcheck.offsetMs).toBe(10000);
  expect(timelineSpan(state.stages)).toBe(40000);
});

test("completing the run replaces the streamed report with the final one", () => {
  const state = play([
    { event: "run_started", data: { ts: T0 } },
    { event: "token", data: { text: "partial" } },
    { event: "run_completed", data: { result: { report: "final report", total_ms: 1000 } } },
  ]);
  expect(state.status).toBe("done");
  expect(state.report).toBe("final report");
});

test("a failed run surfaces the error", () => {
  const state = play([
    { event: "run_started", data: { ts: T0 } },
    { event: "run_failed", data: { error: "Search failed." } },
  ]);
  expect(state.status).toBe("error");
  expect(state.error).toBe("Search failed.");
});

test("unknown events leave the state untouched", () => {
  const before = startState("x");
  expect(reduce(before, { event: "something_new", data: {} })).toBe(before);
});

test("starting a run clears the previous one", () => {
  const finished = play([
    { event: "run_started", data: { ts: T0 } },
    { event: "token", data: { text: "old" } },
  ]);
  const fresh = startState("new topic");
  expect(fresh.report).toBe("");
  expect(fresh.topic).toBe("new topic");
  expect(finished.report).toBe("old");
  expect(initialState.status).toBe("idle");
});
