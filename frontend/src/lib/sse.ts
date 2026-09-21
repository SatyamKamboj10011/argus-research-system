/**
 * Minimal server-sent-events parser.
 *
 * EventSource only speaks GET, and the API key must travel in a request body
 * rather than a URL, so the stream is read from `fetch` by hand. Kept pure and
 * separate from the network call so it can be tested without a server.
 */

export interface SseMessage {
  event: string;
  data: Record<string, unknown>;
}

/** Split a raw SSE buffer into complete messages, returning the unconsumed tail. */
export function parseChunk(buffer: string): { events: SseMessage[]; tail: string } {
  const events: SseMessage[] = [];
  // An SSE message ends at a blank line. Tolerate CRLF from proxies.
  const parts = buffer.replace(/\r\n/g, "\n").split("\n\n");
  const tail = parts.pop() ?? "";

  for (const part of parts) {
    if (!part.trim()) continue;

    let name = "message";
    const dataLines: string[] = [];

    for (const line of part.split("\n")) {
      if (line.startsWith(":")) continue; // comment / keep-alive
      const colon = line.indexOf(":");
      const field = colon === -1 ? line : line.slice(0, colon);
      const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");

      if (field === "event") name = value;
      else if (field === "data") dataLines.push(value);
    }

    if (!dataLines.length) continue;

    const raw = dataLines.join("\n");
    try {
      events.push({ event: name, data: JSON.parse(raw) });
    } catch {
      events.push({ event: name, data: { raw } });
    }
  }

  return { events, tail };
}

/** Read a fetch Response body as a sequence of SSE events. */
export async function* readEvents(
  response: Response,
  signal?: AbortSignal
): AsyncGenerator<SseMessage> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const { events, tail } = parseChunk(buffer);
      buffer = tail;

      for (const event of events) yield event;
      if (signal?.aborted) return;
    }

    const { events } = parseChunk(buffer + "\n\n");
    for (const event of events) yield event;
  } finally {
    reader.cancel().catch(() => {});
  }
}
