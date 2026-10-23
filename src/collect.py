#!/usr/bin/env python3
"""Parse pier job directories into results/pool.csv (one row per trial).

Also a spend guard: --cap exits non-zero if cumulative cost exceeds the cap.

Usage:
    python src/collect.py jobs/ --out results/pool.csv [--cap 60]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


def _dt(s: str | None) -> datetime | None:
    """Parse ISO datetime, handling Z suffix."""
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def collect(jobs_dir: Path) -> pd.DataFrame:
    """Walk Pier result.json files and extract per-trial metrics.

    Expected layout:
        jobs_dir/<job_name>/<trial_name>/result.json
        jobs_dir/<job_name>/<trial_name>/agent/model.patch  (optional)
    """
    rows: list[dict] = []

    for result_path in sorted(jobs_dir.glob("*/*/result.json")):
        r = json.loads(result_path.read_text())
        agent_result = r.get("agent_result") or {}
        verifier = (r.get("verifier_result") or {}).get("rewards") or {}

        t0 = _dt(r.get("started_at"))
        t1 = _dt(r.get("finished_at"))
        latency = (t1 - t0).total_seconds() if t0 and t1 else None

        # Find patch file
        patches = list(result_path.parent.rglob("model.patch"))

        rows.append(
            dict(
                job=result_path.parent.parent.name,
                trial=r.get("trial_name"),
                task=r.get("task_name"),
                passed=int(verifier.get("reward", 0) >= 1) if verifier else 0,
                errored=int(
                    r.get("exception_info") is not None or not verifier
                ),
                cost_usd=agent_result.get("cost_usd") or 0.0,
                in_tokens=agent_result.get("n_input_tokens") or 0,
                out_tokens=agent_result.get("n_output_tokens") or 0,
                model_calls=agent_result.get("n_agent_steps")
                or r.get("n_agent_steps")
                or 0,
                latency_s=latency,
                patch_path=str(patches[0]) if patches else "",
            )
        )

    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Collect Pier trial results into a CSV."
    )
    ap.add_argument("jobs_dir", type=Path, help="Root pier jobs directory")
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("results/pool.csv"),
        help="Output CSV path",
    )
    ap.add_argument(
        "--cap",
        type=float,
        default=None,
        help="Abort if total cost exceeds this USD amount",
    )
    args = ap.parse_args()

    df = collect(args.jobs_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)

    total = df.cost_usd.sum()
    print(
        f"{len(df)} trials, {df.passed.sum()} passed, "
        f"{df.errored.sum()} errored, total ${total:.2f}"
    )

    if args.cap is not None and total > args.cap:
        print(
            f"SPEND GUARD: ${total:.2f} > cap ${args.cap:.2f}",
            file=sys.stderr,
        )
        sys.exit(2)
