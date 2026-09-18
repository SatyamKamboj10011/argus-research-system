export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.round(seconds % 60)}s`;
}

export function scoreColour(value: number): string {
  if (value >= 8) return "var(--color-good)";
  if (value >= 6) return "var(--color-fair)";
  return "var(--color-poor)";
}

export function scoreTone(value: number): "good" | "fair" | "poor" {
  if (value >= 8) return "good";
  if (value >= 6) return "fair";
  return "poor";
}

export function recommendationCopy(recommendation?: string): string {
  if (recommendation === "APPROVE") return "Approved by the critic";
  if (recommendation === "REJECT") return "Rejected by the critic";
  return "The critic wants revisions";
}

export function recommendationTone(recommendation?: string): "good" | "fair" | "poor" {
  if (recommendation === "APPROVE") return "good";
  if (recommendation === "REJECT") return "poor";
  return "fair";
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function slugify(text: string, max = 40): string {
  const slug = text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .slice(0, max)
    // Trim after slicing: a cut landing mid-word would otherwise leave a
    // trailing dash in the filename.
    .replace(/^-+|-+$/g, "");
  return slug || "research";
}

const SCORE_LINE =
  /^\s*[-*]?\s*(Factual Accuracy|Depth of Analysis|Structure (?:&|and) Clarity|Use of Sources|Completeness|Professional Quality)\s*:\s*[\d.]+\s*\/\s*10\s*$/gim;

/**
 * Remove the machine-readable scoring block from a critique.
 *
 * The scores are already drawn as bars, so repeating them as text is noise. What
 * is left is the part only prose can carry: strengths, gaps and the verdict.
 */
export function stripScoreBlock(text?: string): string {
  if (!text) return "";
  return text
    .replace(/^\s*Overall\s+Score\s*:.*$/gim, "")
    .replace(/^\s*Category\s+Scores\s*:\s*$/gim, "")
    .replace(SCORE_LINE, "")
    .replace(/^\s*Fact\s*Check\s*Score\s*:.*$/gim, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function download(content: string, filename: string, type = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
