import { motion, useReducedMotion } from "motion/react";
import { CountUp } from "@/components/ui/motion-primitives";
import { Badge } from "@/components/ui/badge";
import { recommendationCopy, recommendationTone, scoreColour } from "@/lib/format";
import type { Scores } from "@/lib/types";

/**
 * The system grades its own work, so the grade belongs on the document.
 *
 * A ring rather than a bar: the score is a single summary judgement, and the
 * shape keeps it distinct from the per-category bars further down.
 */
export function ScoreGauge({ scores }: { scores: Scores }) {
  const reduce = useReducedMotion();
  if (scores.overall === undefined) return null;

  const value = scores.overall;
  const colour = scoreColour(value);
  const radius = 26;
  const circumference = 2 * Math.PI * radius;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      className="flex items-center gap-4 rounded-2xl border border-line bg-surface/70 p-4 backdrop-blur-sm"
    >
      <div className="relative shrink-0">
        <svg width="68" height="68" viewBox="0 0 68 68" className="-rotate-90">
          <circle
            cx="34"
            cy="34"
            r={radius}
            fill="none"
            stroke="var(--color-elevated)"
            strokeWidth="5"
          />
          <motion.circle
            cx="34"
            cy="34"
            r={radius}
            fill="none"
            stroke={colour}
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference * (1 - value / 10) }}
            transition={reduce ? { duration: 0 } : { duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-lg font-medium tabular-nums leading-none text-ink">
            <CountUp value={value} decimals={1} />
          </span>
          <span className="text-[9px] leading-none text-faint">/ 10</span>
        </div>
      </div>

      <div className="min-w-0 space-y-1.5">
        {scores.recommendation && (
          <Badge tone={recommendationTone(scores.recommendation)}>
            {recommendationCopy(scores.recommendation)}
          </Badge>
        )}
        {scores.verdict && (
          <p className="text-sm leading-relaxed text-muted">{scores.verdict}</p>
        )}
      </div>
    </motion.div>
  );
}

const CATEGORY_ORDER = [
  "Factual Accuracy",
  "Depth of Analysis",
  "Structure & Clarity",
  "Use of Sources",
  "Completeness",
  "Professional Quality",
];

export function ScoreBars({ categories }: { categories: Record<string, number> }) {
  const reduce = useReducedMotion();
  const rows = CATEGORY_ORDER.filter((name) => categories[name] !== undefined);
  if (!rows.length) return null;

  return (
    <div className="space-y-3">
      {rows.map((name, index) => (
        <div key={name} className="grid grid-cols-[9.5rem_1fr_2.25rem] items-center gap-3 text-sm">
          <span className="truncate text-muted">{name}</span>
          <span className="h-1.5 overflow-hidden rounded-full bg-elevated">
            <motion.span
              className="block h-full rounded-full"
              style={{ background: scoreColour(categories[name]) }}
              initial={{ width: 0 }}
              animate={{ width: `${categories[name] * 10}%` }}
              transition={
                reduce
                  ? { duration: 0 }
                  : { duration: 0.8, delay: index * 0.06, ease: [0.16, 1, 0.3, 1] }
              }
            />
          </span>
          <span className="text-right font-mono text-xs tabular-nums text-muted">
            {categories[name].toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  );
}
