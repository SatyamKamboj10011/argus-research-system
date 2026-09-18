import { readEvents } from "./sse";
import type { ModelRow } from "./types";

export const API_URL = (
  import.meta.env.VITE_API_URL || "https://argus-research-system.onrender.com"
).replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return body.detail[0]?.msg ?? "Invalid request.";
  } catch {
    /* fall through to the status-based message */
  }
  return `Request failed (${response.status}).`;
}

/** Wake a sleeping free-tier dyno and report whether the API is reachable. */
export async function ping(timeoutMs = 8000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_URL}/`, { signal: controller.signal });
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchModels(): Promise<{ models: ModelRow[]; default: string }> {
  const response = await fetch(`${API_URL}/api/models`);
  if (!response.ok) throw new ApiError(await readError(response), response.status);
  return response.json();
}

/** Ask the server to typeset a finished run, and hand the file to the browser. */
export async function exportPdf(payload: Record<string, unknown>, filename: string) {
  const response = await fetch(`${API_URL}/api/export/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new ApiError(await readError(response), response.status);

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/**
 * Start a streaming run.
 *
 * `onEvent` is called for every pipeline event as it arrives. Resolves when the
 * stream closes; throws if the request itself is rejected.
 */
export async function streamResearch({
  topic,
  model,
  apiKey,
  signal,
  onEvent,
}: {
  topic: string;
  model: string;
  apiKey?: string;
  signal?: AbortSignal;
  onEvent: (event: string, data: Record<string, unknown>) => void;
}) {
  const response = await fetch(`${API_URL}/api/research/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ topic, model, api_key: apiKey || null }),
    signal,
  });

  if (!response.ok) throw new ApiError(await readError(response), response.status);
  if (!response.body) throw new ApiError("This browser cannot read streamed responses.", 0);

  for await (const { event, data } of readEvents(response, signal)) {
    onEvent(event, data);
  }
}
