import { expect, test } from "vitest";
import { parseChunk } from "./sse";

test("parses a complete event", () => {
  const { events, tail } = parseChunk('event: token\ndata: {"text":"hello"}\n\n');
  expect(events).toEqual([{ event: "token", data: { text: "hello" } }]);
  expect(tail).toBe("");
});

test("holds back a partial event until the rest arrives", () => {
  const first = parseChunk('event: token\ndata: {"text":"par');
  expect(first.events).toHaveLength(0);
  expect(first.tail).toBe('event: token\ndata: {"text":"par');

  const second = parseChunk(first.tail + 'tial"}\n\n');
  expect(second.events).toEqual([{ event: "token", data: { text: "partial" } }]);
});

test("parses several events from one chunk", () => {
  const { events } = parseChunk(
    'event: stage_started\ndata: {"stage":"search"}\n\n' +
      'event: stage_completed\ndata: {"stage":"search","duration_ms":1200}\n\n'
  );
  expect(events.map((e) => e.event)).toEqual(["stage_started", "stage_completed"]);
  expect(events[1].data.duration_ms).toBe(1200);
});

test("tolerates CRLF line endings from proxies", () => {
  const { events } = parseChunk('event: open\r\ndata: {"topic":"x"}\r\n\r\n');
  expect(events).toEqual([{ event: "open", data: { topic: "x" } }]);
});

test("ignores keep-alive comments", () => {
  const { events } = parseChunk(': keep-alive\n\nevent: token\ndata: {"text":"a"}\n\n');
  expect(events).toHaveLength(1);
});

test("joins multi-line data fields", () => {
  const { events } = parseChunk('event: token\ndata: {"text":\ndata: "wrapped"}\n\n');
  expect(events[0].data.text).toBe("wrapped");
});

test("does not throw on malformed JSON", () => {
  const { events } = parseChunk("event: token\ndata: not json\n\n");
  expect(events[0].data).toEqual({ raw: "not json" });
});

test("defaults to the message event when none is named", () => {
  const { events } = parseChunk('data: {"a":1}\n\n');
  expect(events[0].event).toBe("message");
});
