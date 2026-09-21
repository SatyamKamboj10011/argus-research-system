import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowRight,
  Check,
  Copy,
  Database,
  Download,
  ExternalLink,
  FileDown,
  FileJson,
  FileText,
  Loader2,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SpotlightCard } from "@/components/ui/motion-primitives";
import { ScoreBars, ScoreGauge } from "@/components/ScoreGauge";
import { exportPdf } from "@/lib/api";
import { Timeline } from "@/components/pipeline/Timeline";
import {
  download,
  formatDuration,
  hostOf,
  scoreTone,
  slugify,
  stripScoreBlock,
} from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PageRow, RunState } from "@/lib/types";

const FADE = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3 },
};

export function Workspace({
  run,
  onResearchTopic,
}: {
  run: RunState;
  onResearchTopic: (topic: string) => void;
}) {
  const [view, setView] = useState("report");
  const result = run.result;
  const streaming = run.status === "running" && !result;
  const readCount = run.pages.filter((page) => !page.error).length;

  const tabs = useMemo(
    () => [
      { id: "report", label: "Report" },
      { id: "critique", label: "Critique" },
      { id: "facts", label: "Fact check" },
      { id: "sources", label: "Sources", count: run.sources.length },
      { id: "followup", label: "Next questions", count: result?.followup_questions?.length ?? 0 },
    ],
    [result, run.sources.length]
  );

  return (
    // On a narrow screen the document follows the timeline directly; the source
    // list drops below it rather than pushing the report a screen and a half down.
    <div className="mx-auto grid w-full max-w-350 gap-x-8 gap-y-10 px-5 pb-40 pt-8 lg:grid-cols-[19rem_minmax(0,1fr)] lg:grid-rows-[min-content_1fr] lg:gap-y-8 lg:px-8">
      <aside className="space-y-4 lg:col-start-1 lg:row-start-1 lg:sticky lg:top-20 lg:self-start">
        <Timeline stages={run.stages} running={run.status === "running"} />

        {run.cached && (
          <p className="flex items-center gap-1.5 text-[11px] text-faint">
            <Database className="size-3" />
            Replayed from cache — no tokens spent
          </p>
        )}
      </aside>

      <main className="min-w-0 lg:col-start-2 lg:row-start-1 lg:row-span-2">
        {run.error && (
          <motion.div
            {...FADE}
            role="alert"
            className="mb-6 rounded-xl border border-poor/25 bg-poor/5 px-4 py-3 text-sm text-poor"
          >
            {run.error}
          </motion.div>
        )}

        {run.notices.map((notice, index) => (
          <div
            key={index}
            className="mb-4 rounded-xl border border-fair/25 bg-fair/5 px-4 py-3 text-sm text-fair"
          >
            {notice}
          </div>
        ))}

        <header className="space-y-4">
          <h1 className="font-serif text-[clamp(1.9rem,3.4vw,2.7rem)] font-semibold leading-[1.12] tracking-[-0.02em]">
            {run.topic}
          </h1>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px] text-faint">
            {run.modelLabel && <span>{run.modelLabel}</span>}
            {result?.total_ms ? (
              <span className="font-mono tabular-nums">{formatDuration(result.total_ms)}</span>
            ) : null}
            {run.sources.length > 0 && (
              <span>
                <span className="font-mono tabular-nums">{run.sources.length}</span> sources,{" "}
                <span className="font-mono tabular-nums">{readCount}</span> read in full
              </span>
            )}
            {result?.fact_check_summary?.score !== undefined && (
              <Badge tone={scoreTone(result.fact_check_summary.score)}>
                {result.fact_check_summary.verdict?.toLowerCase()}
              </Badge>
            )}
          </div>

          {result?.scores && <ScoreGauge scores={result.scores} />}
        </header>

        <Tabs value={view} onValueChange={setView} className="mt-8">
          <TabsList>
            {tabs.map((tab) => (
              <TabsTrigger key={tab.id} value={tab.id} active={view === tab.id}>
                {tab.label}
                {tab.count ? (
                  <span className="font-mono text-[11px] tabular-nums text-faint">{tab.count}</span>
                ) : null}
              </TabsTrigger>
            ))}
          </TabsList>

          <div className="pt-7">
            <AnimatePresence mode="wait">
              <motion.div key={view} {...FADE}>
                <TabsContent value="report" forceMount={view === "report" ? true : undefined}>
                  {view === "report" &&
                    (run.report ? (
                      <article className="report max-w-[68ch]">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{run.report}</ReactMarkdown>
                        {streaming && (
                          <span className="ml-0.5 inline-block h-[1.05em] w-[0.45em] translate-y-[0.15em] rounded-[1px] bg-linear-to-b from-iris to-cyan align-baseline motion-safe:animate-pulse" />
                        )}
                      </article>
                    ) : (
                      <Waiting label="The report streams in here as it is written." />
                    ))}
                </TabsContent>

                <TabsContent value="critique">
                  {view === "critique" && (
                    <div className="max-w-[68ch] space-y-8">
                      {result?.scores?.categories && (
                        <ScoreBars categories={result.scores.categories} />
                      )}
                      <Commentary
                        text={result?.critic}
                        empty="The critic runs once the report is written."
                      />
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="facts">
                  {view === "facts" && (
                    <div className="max-w-[68ch]">
                      <Commentary
                        text={result?.factcheck}
                        empty="Claims are checked against the sources once the report is written."
                      />
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="sources">
                  {view === "sources" && (
                    <div className="space-y-8">
                      {run.sources.length === 0 ? (
                        <Waiting label="Sources appear as the search agent finds them." />
                      ) : (
                        <div className="grid gap-3 sm:grid-cols-2">
                          {run.sources.map((source) => {
                            const page = run.pages.find((row) => pageMatches(row, source.url));
                            return (
                              <SpotlightCard
                                key={source.url}
                                className="rounded-xl border border-line bg-surface/60 transition-colors hover:border-line-bright"
                              >
                                <a
                                  href={source.url}
                                  target="_blank"
                                  rel="noreferrer noopener"
                                  className="block p-4"
                                >
                                  <div className="flex items-start justify-between gap-3">
                                    <p className="font-medium leading-snug text-ink">
                                      {source.title}
                                    </p>
                                    <ExternalLink className="mt-0.5 size-3.5 shrink-0 text-faint" />
                                  </div>
                                  <p className="mt-1.5 text-xs text-faint">
                                    {source.domain || hostOf(source.url)}
                                  </p>
                                  {source.snippet && (
                                    <p className="mt-2.5 line-clamp-3 text-[13px] leading-relaxed text-muted">
                                      {source.snippet}
                                    </p>
                                  )}
                                  {page && (
                                    <p className="mt-3 text-[11px] text-faint">
                                      {page.error
                                        ? `Could not be read: ${page.error}`
                                        : `Read in full — ${page.chars?.toLocaleString()} characters`}
                                    </p>
                                  )}
                                </a>
                              </SpotlightCard>
                            );
                          })}
                        </div>
                      )}

                      {result?.credibility && (
                        <section className="max-w-[68ch] space-y-3">
                          <h2 className="text-sm font-medium text-ink">How credible are they?</h2>
                          <Commentary text={result.credibility} empty="" />
                        </section>
                      )}
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="followup">
                  {view === "followup" &&
                    (result?.followup_questions?.length ? (
                      <div className="grid max-w-3xl gap-2.5">
                        {result.followup_questions.map((question, index) => (
                          <motion.button
                            key={question}
                            initial={{ opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: index * 0.05, duration: 0.35 }}
                            type="button"
                            onClick={() => onResearchTopic(question)}
                            className="group flex items-start gap-3 rounded-xl border border-line bg-surface/60 p-4 text-left transition-all duration-200 hover:border-iris/40 hover:bg-iris/5"
                          >
                            <span className="mt-0.5 font-mono text-xs tabular-nums text-faint">
                              {index + 1}
                            </span>
                            <span className="flex-1 text-[15px] leading-relaxed text-muted transition-colors group-hover:text-ink">
                              {question}
                            </span>
                            <ArrowRight className="mt-1 size-4 shrink-0 text-faint transition-all duration-200 group-hover:translate-x-0.5 group-hover:text-iris-soft" />
                          </motion.button>
                        ))}
                      </div>
                    ) : (
                      <Waiting label="Follow-up questions are proposed once the report is written." />
                    ))}
                </TabsContent>
              </motion.div>
            </AnimatePresence>
          </div>
        </Tabs>

        {result && <Exports run={run} />}
      </main>

      <aside className="lg:col-start-1 lg:row-start-2 lg:pb-8">
        {run.sources.length > 0 && (
          <section className="space-y-2">
            <h2 className="text-xs font-medium text-faint">
              Sources <span className="font-mono tabular-nums">{run.sources.length}</span>
            </h2>
            <div className="space-y-px">
              {run.sources.map((source) => {
                const wasRead = run.pages.some((page) => pageMatches(page, source.url) && !page.error);
                return (
                  <a
                    key={source.url}
                    href={source.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="group block rounded-lg px-2 py-2 -mx-2 transition-colors hover:bg-elevated"
                  >
                    <p className="line-clamp-2 text-[13px] leading-snug text-muted transition-colors group-hover:text-ink">
                      {source.title}
                    </p>
                    <p className="mt-1 flex items-center gap-1.5 text-[11px] text-faint">
                      {source.domain || hostOf(source.url)}
                      {wasRead && <span className="text-good">· read in full</span>}
                    </p>
                  </a>
                );
              })}
            </div>
          </section>
        )}
      </aside>
    </div>
  );
}

/** A fetched page is matched to its search result on the URL we asked for, not
    the one we landed on: a redirect changes the latter. */
function pageMatches(page: PageRow, sourceUrl: string): boolean {
  return (page.source_url ?? page.url) === sourceUrl;
}

function Commentary({ text, empty }: { text?: string; empty: string }) {
  const body = stripScoreBlock(text);
  if (!body) return empty ? <Waiting label={empty} /> : null;
  return (
    <div className="commentary">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
    </div>
  );
}

function Waiting({ label }: { label: string }) {
  return (
    <div className="max-w-[68ch] space-y-3">
      <p className="text-sm text-faint">{label}</p>
      {[92, 78, 85, 64].map((width, index) => (
        <div
          key={width}
          className="h-3 rounded bg-linear-to-r from-elevated via-raised to-elevated bg-[length:200%_100%] motion-safe:animate-pulse"
          style={{ width: `${width}%`, animationDelay: `${index * 120}ms` }}
        />
      ))}
    </div>
  );
}

function Exports({ run }: { run: RunState }) {
  const [copied, setCopied] = useState(false);
  const [pdfState, setPdfState] = useState<"idle" | "working" | "failed">("idle");
  const result = run.result!;
  const stem = slugify(run.topic);

  async function downloadPdf() {
    setPdfState("working");
    try {
      await exportPdf(
        {
          topic: run.topic,
          report: result.report,
          critic: result.critic ?? "",
          factcheck: result.factcheck ?? "",
          model_label: run.modelLabel ?? "",
          total_ms: result.total_ms ?? 0,
          scores: result.scores ?? {},
          sources: run.sources,
          pages: run.pages,
        },
        `${stem}.pdf`
      );
      setPdfState("idle");
    } catch {
      setPdfState("failed");
      setTimeout(() => setPdfState("idle"), 3000);
    }
  }

  async function copyReport() {
    try {
      await navigator.clipboard.writeText(result.report);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  function downloadMarkdown() {
    const body = [
      `# ${run.topic}`,
      "",
      `Researched with ${run.modelLabel || "Argus"} in ${formatDuration(result.total_ms)}.`,
      result.scores?.overall !== undefined
        ? `Critic score: ${result.scores.overall}/10 — ${result.scores.recommendation ?? ""}`
        : "",
      "",
      result.report,
      "",
      "## Critique",
      "",
      result.critic || "Not available.",
      "",
      "## Fact check",
      "",
      result.factcheck || "Not available.",
      "",
      "## Sources",
      "",
      run.sources.map((source) => `- [${source.title}](${source.url})`).join("\n"),
    ].join("\n");
    download(body, `${stem}.md`, "text/markdown;charset=utf-8");
  }

  return (
    <div className={cn("mt-14 flex flex-wrap gap-2 border-t border-line pt-6")}>
      <Button variant="secondary" size="sm" onClick={copyReport}>
        {copied ? <Check className="text-good" /> : <Copy />}
        {copied ? "Copied" : "Copy report"}
      </Button>
      <Button
        variant="secondary"
        size="sm"
        onClick={downloadPdf}
        disabled={pdfState === "working"}
      >
        {pdfState === "working" ? <Loader2 className="animate-spin" /> : <FileDown />}
        {pdfState === "working" ? "Typesetting…" : pdfState === "failed" ? "PDF failed" : "PDF"}
      </Button>
      <Button variant="secondary" size="sm" onClick={downloadMarkdown}>
        <FileText />
        Markdown
      </Button>
      <Button
        variant="secondary"
        size="sm"
        onClick={() =>
          download(JSON.stringify(result, null, 2), `${stem}.json`, "application/json")
        }
      >
        <FileJson />
        JSON
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => download(result.search_results, `${stem}-sources.txt`)}
      >
        <Download />
        Raw sources
      </Button>
    </div>
  );
}
