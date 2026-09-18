#!/usr/bin/env python
"""Probe every registry entry against its provider and report what is still live.

Model ids rot. This project already shipped a registry pointing at Groq's
``llama-3.3-70b-versatile`` months after it was retired, which meant every run
failed at the writer stage with a 404. Run this after a provider announcement, or
on a schedule, to catch that before a user does.

Usage::

    python scripts/check_models.py           # probe providers you have keys for
    python scripts/check_models.py --json    # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Runnable as `python scripts/check_models.py` without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from argus.llm import REGISTRY, MissingCredentialsError, get_llm

PROBE = [("user", "Reply with the single word: ok")]


def probe(spec) -> dict:
    row = {"id": spec.id, "model": spec.model_name, "provider": spec.provider}
    try:
        llm = get_llm(spec.id)
    except MissingCredentialsError as exc:
        return {**row, "status": "skipped", "detail": str(exc)[:70]}
    except Exception as exc:
        return {**row, "status": "error", "detail": f"init failed: {exc}"}

    try:
        reply = llm.invoke(PROBE)
        text = (reply.content if hasattr(reply, "content") else str(reply)) or ""
        return {**row, "status": "live", "detail": str(text)[:60].strip()}
    except Exception as exc:
        message = str(exc)
        lowered = message.lower()
        if "model_not_found" in lowered or "does not exist" in lowered:
            return {**row, "status": "RETIRED", "detail": "provider no longer serves this model"}
        if "rate" in lowered and "limit" in lowered:
            return {**row, "status": "live", "detail": "rate limited, but the model exists"}
        return {**row, "status": "error", "detail": message[:160]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = parser.parse_args()

    rows = [probe(spec) for spec in REGISTRY]

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        width = max(len(r["id"]) for r in rows)
        for row in rows:
            mark = {"live": "OK ", "RETIRED": "GONE", "skipped": "SKIP", "error": "ERR"}.get(
                row["status"], "?"
            )
            print(f"{mark:5} {row['id']:<{width}}  {row['model']:<28} {row['detail']}")

    retired = [r for r in rows if r["status"] == "RETIRED"]
    if retired:
        print(
            f"\n{len(retired)} registry entr{'y is' if len(retired) == 1 else 'ies are'} "
            "pointing at a retired model. Update argus/llm.py.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
