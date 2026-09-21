import { describe, expect, test } from "vitest";
import {
  formatDuration,
  hostOf,
  recommendationTone,
  scoreTone,
  slugify,
  stripScoreBlock,
} from "./format";

describe("formatDuration", () => {
  test.each([
    [0, "0ms"],
    [880, "880ms"],
    [1200, "1.2s"],
    [9949, "9.9s"],
    [12000, "12s"],
    [75000, "1m 15s"],
    [3_600_000, "60m 0s"],
  ])("%ims renders as %s", (ms, expected) => {
    expect(formatDuration(ms)).toBe(expected);
  });

  test("renders nothing for a missing duration", () => {
    expect(formatDuration(null)).toBe("");
    expect(formatDuration(undefined)).toBe("");
  });
});

describe("scoreTone", () => {
  test.each([
    [10, "good"],
    [8, "good"],
    [7.9, "fair"],
    [6, "fair"],
    [5.9, "poor"],
    [0, "poor"],
  ])("%s is %s", (value, expected) => {
    expect(scoreTone(value as number)).toBe(expected);
  });
});

test("recommendation maps to a tone", () => {
  expect(recommendationTone("APPROVE")).toBe("good");
  expect(recommendationTone("REJECT")).toBe("poor");
  expect(recommendationTone("NEEDS REVISION")).toBe("fair");
  expect(recommendationTone(undefined)).toBe("fair");
});

describe("hostOf", () => {
  test("strips the scheme and www", () => {
    expect(hostOf("https://www.reuters.com/world/article")).toBe("reuters.com");
  });

  test("returns the input unchanged when it is not a URL", () => {
    expect(hostOf("not a url")).toBe("not a url");
  });
});

describe("slugify", () => {
  test("builds a filename stem", () => {
    expect(slugify("How rare earth controls reshaped supply chains!")).toBe(
      "how-rare-earth-controls-reshaped-supply"
    );
  });

  test("never returns an empty stem", () => {
    expect(slugify("!!!")).toBe("research");
    expect(slugify("")).toBe("research");
  });

  test("does not leave a trailing dash after truncation", () => {
    expect(slugify("aaaaaaaaaa bbbbbbbbbb cccccccccc dddddddddd eeee")).not.toMatch(/-$/);
  });
});

describe("stripScoreBlock", () => {
  const critique = `Overall Score: 7.5/10

Category Scores:
- Factual Accuracy: 8/10
- Depth of Analysis: 7/10
- Structure & Clarity: 9/10
- Use of Sources: 6/10
- Completeness: 7/10
- Professional Quality: 8/10

Strengths:
- Clear structure throughout.

One-Line Verdict: Well organised but thinly sourced.`;

  test("removes every line the score bars already show", () => {
    const out = stripScoreBlock(critique);
    expect(out).not.toMatch(/Overall Score/);
    expect(out).not.toMatch(/Factual Accuracy: 8\/10/);
    expect(out).not.toMatch(/Category Scores/);
  });

  test("keeps the prose that only text can carry", () => {
    const out = stripScoreBlock(critique);
    expect(out).toContain("Clear structure throughout.");
    expect(out).toContain("One-Line Verdict");
  });

  test("collapses the gaps left behind", () => {
    expect(stripScoreBlock(critique)).not.toMatch(/\n{3,}/);
  });

  test("handles the 'and' spelling and markdown bullets", () => {
    expect(stripScoreBlock("* Structure and Clarity: 5/10\nkeep me")).toBe("keep me");
  });

  test("is safe on empty input", () => {
    expect(stripScoreBlock(undefined)).toBe("");
    expect(stripScoreBlock("")).toBe("");
  });
});
