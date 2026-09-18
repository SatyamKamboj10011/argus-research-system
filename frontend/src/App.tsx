import { Suspense, lazy, useCallback, useEffect, useReducer, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Hero } from "@/components/Hero";
import { Composer } from "@/components/Composer";

// The workspace pulls in the Markdown renderer, which is dead weight on the
// landing screen. Loading it when the first run starts keeps the entry small.
const Workspace = lazy(() =>
  import("@/components/Workspace").then((m) => ({ default: m.Workspace }))
);
import { ApiError, fetchModels, ping, streamResearch } from "@/lib/api";
import { initialState, reduce, startState } from "@/lib/runState";
import { cn } from "@/lib/utils";
import type { ModelRow, PipelineEvent, RunState } from "@/lib/types";

const FALLBACK_MODELS: ModelRow[] = [
  {
    id: "groq-gpt-oss-120b",
    label: "GPT-OSS 120B",
    provider: "groq",
    description: "Best overall quality.",
    context_window: 131072,
    is_local: false,
    recommended: true,
    ready: true,
    key_env_var: "GROQ_API_KEY",
  },
];

type Action = PipelineEvent | { type: "reset"; topic: string };

function runReducer(state: RunState, action: Action): RunState {
  if ("type" in action && action.type === "reset") return startState(action.topic);
  return reduce(state, action as PipelineEvent);
}

export default function App() {
  const [run, dispatch] = useReducer(runReducer, initialState);
  const [topic, setTopic] = useState("");
  const [models, setModels] = useState<ModelRow[]>(FALLBACK_MODELS);
  const [model, setModel] = useState(FALLBACK_MODELS[0].id);
  const [apiKey, setApiKey] = useState("");
  const [apiReachable, setApiReachable] = useState<boolean | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const busy = run.status === "connecting" || run.status === "running";
  const landing = run.status === "idle";

  // Wake the free-tier backend and load the model catalogue up front, so the
  // model list can never drift from what the server actually supports.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const health = await ping();
      if (cancelled) return;
      setApiReachable(Boolean(health));
      if (!health) return;
      try {
        const catalogue = await fetchModels();
        if (cancelled || !catalogue.models?.length) return;
        setModels(catalogue.models);
        const preferred =
          catalogue.models.find((row) => row.id === catalogue.default && row.ready) ??
          catalogue.models.find((row) => row.ready) ??
          catalogue.models[0];
        setModel(preferred.id);
      } catch {
        /* keep the fallback catalogue */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    document.title = run.topic ? `${run.topic} — Argus` : "Argus — research that shows its working";
  }, [run.topic]);

  const start = useCallback(
    async (nextTopic?: string) => {
      const subject = (nextTopic ?? topic).trim();
      if (subject.length < 3 || busy) return;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      dispatch({ type: "reset", topic: subject });
      window.scrollTo({ top: 0, behavior: "smooth" });

      try {
        await streamResearch({
          topic: subject,
          model,
          apiKey,
          signal: controller.signal,
          onEvent: (event, data) => dispatch({ event, data }),
        });
      } catch (error) {
        if (controller.signal.aborted) return;
        const message =
          error instanceof ApiError
            ? error.message
            : error instanceof Error
              ? error.message
              : "Could not reach the research API.";
        dispatch({ event: "run_failed", data: { error: message } });
      }
    },
    [apiKey, busy, model, topic]
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ event: "run_failed", data: { error: "Run stopped." } });
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  const researchTopic = useCallback(
    (question: string) => {
      setTopic(question);
      start(question);
    },
    [start]
  );

  const composer = (
    <Composer
      topic={topic}
      onTopicChange={setTopic}
      models={models}
      model={model}
      onModelChange={setModel}
      apiKey={apiKey}
      onApiKeyChange={setApiKey}
      onStart={() => start()}
      onStop={stop}
      busy={busy}
      autoFocus={landing}
    />
  );

  return (
    <TooltipProvider delayDuration={300}>
      <div className="relative min-h-dvh">
        <TopBar status={run.status} landing={landing} />

        <AnimatePresence mode="wait">
          {landing ? (
            <motion.div
              key="hero"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.35 }}
            >
              <Hero
                apiReachable={apiReachable}
                composer={composer}
                onPick={(example) => {
                  setTopic(example);
                  start(example);
                }}
              />
            </motion.div>
          ) : (
            <motion.div
              key="workspace"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="pt-14"
            >
              <Suspense fallback={<WorkspaceFallback />}>
                <Workspace run={run} onResearchTopic={researchTopic} />
              </Suspense>
            </motion.div>
          )}
        </AnimatePresence>

        {/* In the workspace the composer docks to the bottom so the next run is
            always one keystroke away. On the landing screen it sits in the flow,
            where it would otherwise cover the cards below it. */}
        {!landing && (
          <>
            {/* Content fades out beneath the docked bar rather than being sliced by it. */}
            <div
              aria-hidden
              className="pointer-events-none fixed inset-x-0 bottom-0 z-30 h-40 bg-linear-to-t from-base via-base/90 to-transparent"
            />
            <motion.div
              initial={{ y: 80, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
              className="fixed inset-x-0 bottom-5 z-40 mx-auto w-full max-w-2xl px-5"
            >
              {composer}
            </motion.div>
          </>
        )}
      </div>
    </TooltipProvider>
  );
}

function WorkspaceFallback() {
  return (
    <div className="mx-auto w-full max-w-350 px-5 pt-8 lg:px-8">
      <div className="h-8 w-2/3 max-w-lg animate-pulse rounded bg-elevated" />
    </div>
  );
}

function TopBar({ status, landing }: { status: RunState["status"]; landing: boolean }) {
  const label =
    status === "connecting"
      ? "connecting"
      : status === "running"
        ? "running"
        : status === "done"
          ? "complete"
          : status === "error"
            ? "failed"
            : "ready";

  const dot =
    status === "error"
      ? "bg-poor"
      : status === "done"
        ? "bg-good"
        : status === "idle"
          ? "bg-faint"
          : "bg-iris-soft";

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-40 flex h-14 items-center justify-between px-5 transition-colors duration-300 lg:px-8",
        landing ? "bg-transparent" : "border-b border-line bg-base/80 backdrop-blur-xl"
      )}
    >
      <a href="/" className="flex items-center gap-2.5">
        <span className="grid size-6 place-items-center rounded-md bg-linear-to-br from-iris to-cyan">
          <span className="size-1.5 rounded-full bg-base" />
        </span>
        <span className="text-[15px] font-semibold tracking-tight">Argus</span>
      </a>

      <div className="flex items-center gap-4">
        <span className="flex items-center gap-2 text-xs text-faint">
          <span className={cn("size-1.5 rounded-full", dot)} />
          {label}
        </span>
        <a
          href="https://github.com/SatyamKamboj10011/argus-research-system"
          target="_blank"
          rel="noreferrer noopener"
          className="text-xs text-faint transition-colors hover:text-ink"
        >
          Source
        </a>
      </div>
    </header>
  );
}
