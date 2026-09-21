import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { AlertTriangle, Check, Loader2 } from "lucide-react";
import { STAGE_DETAIL, STAGE_LABELS, STAGE_ORDER, timelineSpan } from "@/lib/runState";
import { formatDuration } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { StageState } from "@/lib/types";

/**
 * A Gantt chart of the run.
 *
 * Bars are positioned by each stage's real start offset and sized by its real
 * duration, both from the server. The four review stages overlap because they
 * genuinely run concurrently — showing that is the point of the chart.
 */
export function Timeline({
  stages,
  running,
  className,
}: {
  stages: Record<string, StageState>;
  running: boolean;
  className?: string;
}) {
  const [now, setNow] = useState(0);
  const reduce = useReducedMotion();

  // A stage in flight has no end yet, so its bar grows against a local clock.
  // The ticker stops as soon as the run does.
  useEffect(() => {
    if (!running) return undefined;
    const started = Date.now();
    const id = setInterval(() => setNow(Date.now() - started), 100);
    return () => clearInterval(id);
  }, [running]);

  // `!= null` on purpose: before a run the stage map is empty, and a strict
  // comparison against null would treat `undefined` as "started".
  const anyStarted = STAGE_ORDER.some((id) => stages[id]?.offsetMs != null);
  if (!anyStarted) return null;

  const span = timelineSpan(stages, now);

  return (
    <section className={cn("space-y-2.5", className)} aria-label="Pipeline timeline">
      <header className="flex items-baseline justify-between">
        <h2 className="text-xs font-medium text-faint">Pipeline</h2>
        <span className="font-mono text-[11px] tabular-nums text-faint">
          {formatDuration(span)}
        </span>
      </header>

      <div className="space-y-1.5">
        {STAGE_ORDER.map((id, index) => {
          const stage = stages[id] ?? ({ status: "pending", offsetMs: null } as StageState);
          const started = stage.offsetMs != null;
          const offset = stage.offsetMs ?? 0;
          const elapsed =
            stage.durationMs ?? (stage.status === "running" ? Math.max(0, now - offset) : 0);
          const left = started ? (offset / span) * 100 : 0;
          const width = started ? Math.max(1, (elapsed / span) * 100) : 0;

          return (
            <Tooltip key={id} delayDuration={200}>
              <TooltipTrigger asChild>
                <motion.div
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.04, duration: 0.35 }}
                  className="group cursor-default space-y-1 rounded-md px-1 py-0.5 -mx-1 transition-colors hover:bg-elevated/60"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-[13px]">
                      <StageGlyph status={stage.status} />
                      <span
                        className={cn(
                          "transition-colors",
                          stage.status === "pending" ? "text-faint" : "text-ink"
                        )}
                      >
                        {STAGE_LABELS[id]}
                      </span>
                    </span>
                    <span className="font-mono text-[11px] tabular-nums text-faint">
                      {stage.durationMs != null
                        ? formatDuration(stage.durationMs)
                        : stage.status === "running"
                          ? formatDuration(elapsed)
                          : ""}
                    </span>
                  </div>

                  <div className="relative h-1.5 overflow-hidden rounded-full bg-elevated">
                    {started && (
                      <motion.div
                        className={cn(
                          "absolute inset-y-0 rounded-full",
                          stage.status === "failed"
                            ? "bg-poor"
                            : "bg-linear-to-r from-iris to-cyan"
                        )}
                        initial={false}
                        animate={{ left: `${left}%`, width: `${width}%` }}
                        transition={
                          reduce ? { duration: 0 } : { type: "spring", stiffness: 160, damping: 26 }
                        }
                      >
                        {stage.status === "running" && !reduce && (
                          <span className="absolute inset-0 overflow-hidden rounded-full">
                            <span className="absolute inset-y-0 w-1/3 bg-white/35 blur-[2px] animate-sheen" />
                          </span>
                        )}
                      </motion.div>
                    )}
                  </div>
                </motion.div>
              </TooltipTrigger>
              <TooltipContent side="right">
                <p className="font-medium text-ink">{STAGE_LABELS[id]}</p>
                <p className="mt-0.5 text-muted">{stage.error ?? STAGE_DETAIL[id]}</p>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </section>
  );
}

function StageGlyph({ status }: { status: StageState["status"] }) {
  if (status === "done") return <Check className="size-3 text-good" />;
  if (status === "failed") return <AlertTriangle className="size-3 text-poor" />;
  if (status === "running") return <Loader2 className="size-3 animate-spin text-iris-soft" />;
  return <span className="size-3 rounded-full border border-line" />;
}
