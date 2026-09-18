import type * as React from "react";
import { motion } from "motion/react";
import { ArrowUpRight, Globe, Scale, ScanSearch, Sparkles } from "lucide-react";
import { Stagger, WordReveal, staggerItem } from "@/components/ui/motion-primitives";
import { HeroBackdrop } from "@/components/ui/backgrounds";
import { Badge } from "@/components/ui/badge";
import { SpotlightCard } from "@/components/ui/motion-primitives";

const EXAMPLES = [
  "How rare earth export controls reshaped supply chains in 2026",
  "What went wrong with carbon offset markets",
  "The state of small modular reactors",
  "Why RNA vaccines stalled outside COVID",
  "How cities are actually reducing car dependency",
];

const PILLARS = [
  {
    icon: Globe,
    title: "Reads the live web",
    body: "A search agent queries, judges its own results, and requeries when they are thin. The pages it settles on are fetched in parallel and stripped to text.",
  },
  {
    icon: Sparkles,
    title: "Writes with its sources open",
    body: "Claims trace back to retrieved material, attributed inline. Where the evidence is thin, the report says so instead of padding.",
  },
  {
    icon: Scale,
    title: "Then grades its own work",
    body: "Four reviewers run at once: a critic scoring six dimensions, a fact-checker, a source-credibility pass, and the questions you should ask next.",
  },
];

export function Hero({
  onPick,
  apiReachable,
  composer,
}: {
  onPick: (topic: string) => void;
  apiReachable: boolean | null;
  composer: React.ReactNode;
}) {
  return (
    <div className="relative min-h-dvh overflow-hidden">
      <HeroBackdrop />

      <div className="relative mx-auto w-full max-w-5xl px-6 pb-24 pt-24 sm:pt-28">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="flex justify-center"
        >
          <Badge tone="brand" className="gap-2 px-3 py-1">
            <ScanSearch className="size-3.5" />
            Seven agents, one topic
          </Badge>
        </motion.div>

        <h1 className="display relative mt-8 text-center text-[clamp(2.9rem,8.5vw,5.75rem)]">
          <WordReveal text="Research that" delay={0.1} />
          <br />
          <span className="relative inline-block">
            {/* The bloom sits behind the type, not on it: a text-shadow at this
                size smears, a blurred copy stays crisp. */}
            <span
              aria-hidden
              className="pointer-events-none absolute inset-0 -z-10 select-none gradient-text opacity-55 blur-[38px]"
            >
              shows <i>its</i> working
            </span>
            <WordReveal text="shows" delay={0.3} />{" "}
            <WordReveal text="its" className="italic" delay={0.36} />{" "}
            <WordReveal text="working" className="gradient-text" delay={0.42} />
          </span>
        </h1>

        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.55 }}
          className="mx-auto mt-6 max-w-2xl text-center text-lg leading-relaxed text-muted"
        >
          Argus searches the live web, reads what it finds, writes a sourced report, then grades
          itself and tells you where it fell short. Every stage streams as it happens.
        </motion.p>

        {apiReachable === false && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.7 }}
            className="mx-auto mt-8 max-w-xl rounded-xl border border-fair/25 bg-fair/5 px-4 py-3 text-center text-sm text-fair"
          >
            The API has not answered yet. It sleeps on a free tier, so the first run can take about
            a minute to wake it.
          </motion.div>
        )}

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.68, ease: [0.16, 1, 0.3, 1] }}
          className="mx-auto mt-10 max-w-2xl"
        >
          {composer}
        </motion.div>

        <Stagger className="mt-7 flex flex-wrap justify-center gap-2" delay={0.9}>
          {EXAMPLES.map((example) => (
            <motion.button
              key={example}
              variants={staggerItem}
              type="button"
              onClick={() => onPick(example)}
              className="group flex items-center gap-1.5 rounded-full border border-line bg-raised/60 px-3.5 py-1.5 text-sm text-muted backdrop-blur-sm transition-all duration-200 hover:border-iris/40 hover:bg-iris/8 hover:text-ink"
            >
              {example}
              <ArrowUpRight className="size-3.5 opacity-0 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-px" />
            </motion.button>
          ))}
        </Stagger>

        <Stagger className="mt-24 grid gap-4 sm:grid-cols-3" delay={1.05}>
          {PILLARS.map(({ icon: Icon, title, body }) => (
            <motion.div key={title} variants={staggerItem}>
              <SpotlightCard className="h-full rounded-2xl border border-line bg-surface/70 p-5 backdrop-blur-sm transition-colors duration-300 hover:border-line-bright">
                <Icon className="size-5 text-iris-soft" />
                <h3 className="mt-3.5 font-medium text-ink">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{body}</p>
              </SpotlightCard>
            </motion.div>
          ))}
        </Stagger>
      </div>
    </div>
  );
}
