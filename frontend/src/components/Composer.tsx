import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowUp, ChevronDown, Key, Loader2, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { ModelRow } from "@/lib/types";

const MAX_TOPIC = 300;

/**
 * The single place a run is started from.
 *
 * Floats over the page so it stays reachable whether you are on the landing
 * screen or deep in a finished report.
 */
export function Composer({
  topic,
  onTopicChange,
  models,
  model,
  onModelChange,
  apiKey,
  onApiKeyChange,
  onStart,
  onStop,
  busy,
  autoFocus,
}: {
  topic: string;
  onTopicChange: (value: string) => void;
  models: ModelRow[];
  model: string;
  onModelChange: (value: string) => void;
  apiKey: string;
  onApiKeyChange: (value: string) => void;
  onStart: () => void;
  onStop: () => void;
  busy: boolean;
  autoFocus?: boolean;
}) {
  const [showKey, setShowKey] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const selected = models.find((m) => m.id === model);
  const tooLong = topic.length > MAX_TOPIC;
  const canStart = topic.trim().length >= 3 && !tooLong && !busy;

  // Cmd/Ctrl+K focuses the composer from anywhere.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  // Grow with the content rather than scrolling a fixed box.
  useEffect(() => {
    const node = inputRef.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, 160)}px`;
  }, [topic]);

  return (
    <div className="glass rounded-2xl p-2 shadow-[0_24px_60px_-28px_rgba(0,0,0,0.9)]">
      <div className="flex items-end gap-2">
        <textarea
          ref={inputRef}
          rows={1}
          value={topic}
          onChange={(event) => onTopicChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && canStart) {
              event.preventDefault();
              onStart();
            }
          }}
          placeholder="Ask about anything with a public record…"
          disabled={busy}
          className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-[15px] leading-relaxed text-ink outline-none placeholder:text-faint disabled:opacity-60"
        />

        {busy ? (
          <Button variant="secondary" size="icon" onClick={onStop} aria-label="Stop the run">
            <Square className="size-3.5 fill-current" />
          </Button>
        ) : (
          <Button
            variant="primary"
            size="icon"
            onClick={onStart}
            disabled={!canStart}
            aria-label="Start research"
            className={cn(canStart && "animate-pulse-ring")}
          >
            <ArrowUp className="size-4" />
          </Button>
        )}
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-2 border-t border-line px-1 pt-2">
        <Select value={model} onValueChange={onModelChange} disabled={busy}>
          <SelectTrigger
            aria-label="Model"
            className="h-8 w-auto gap-1.5 border-0 bg-transparent px-2 text-xs text-muted hover:bg-elevated"
          >
            {/* The trigger shows the label only; descriptions belong in the menu. */}
            <span className="truncate">{selected?.label ?? "Model"}</span>
          </SelectTrigger>
          <SelectContent>
            {models.map((row) => (
              <SelectItem key={row.id} value={row.id}>
                <span className="flex flex-col gap-0.5 pr-5">
                  <span className="flex items-center gap-1.5 text-ink">
                    {row.label}
                    {row.recommended && <span className="text-[10px] text-iris-soft">best</span>}
                    {!row.ready && <span className="text-[10px] text-fair">needs a key</span>}
                  </span>
                  <span className="text-[11px] leading-tight text-faint">{row.description}</span>
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <button
          type="button"
          onClick={() => setShowKey((value) => !value)}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-faint transition-colors hover:bg-elevated hover:text-muted"
        >
          <Key className="size-3" />
          Your own key
          <ChevronDown
            className={cn("size-3 transition-transform duration-200", showKey && "rotate-180")}
          />
        </button>

        <span className="ml-auto px-1 font-mono text-[11px] tabular-nums text-faint">
          <span className={cn(tooLong && "text-poor")}>{topic.length}</span>/{MAX_TOPIC}
        </span>

        {busy && (
          <span className="flex items-center gap-1.5 px-1 text-xs text-iris-soft">
            <Loader2 className="size-3 animate-spin" />
            running
          </span>
        )}
      </div>

      <AnimatePresence initial={false}>
        {showKey && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="px-1 pb-1 pt-2">
              <input
                type="password"
                value={apiKey}
                onChange={(event) => onApiKeyChange(event.target.value)}
                placeholder={
                  selected?.key_env_var
                    ? `Paste a ${selected.provider} key`
                    : "Paste a provider key"
                }
                autoComplete="off"
                disabled={busy}
                className="h-9 w-full rounded-lg border border-line bg-elevated px-3 text-sm outline-none transition-colors placeholder:text-faint focus:border-iris/50"
              />
              <p className="mt-1.5 px-0.5 text-[11px] leading-relaxed text-faint">
                Sent with this request only. Never stored, logged, or cached on the server.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
