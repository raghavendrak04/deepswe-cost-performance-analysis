#!/usr/bin/env python3
"""Score every pool patch once with the LLM judge; cache to results/judge.csv.

Usage:
    python src/judge_pool.py \\
        --model claude-haiku-4-20250514 \\
        --pin 0.25 --pout 1.25 \\
        --cap 10

Takes prices from the provider price page.
Stops at --cap USD to prevent overspend.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from select_patch import judge_score


def main():
    ap = argparse.ArgumentParser(
        description="Score all pool patches with an LLM judge."
    )
    ap.add_argument(
        "--pool", default="results/pool.csv", help="Pool CSV from collect.py"
    )
    ap.add_argument(
        "--tasks", default="deep-swe/tasks", help="Tasks directory"
    )
    ap.add_argument("--model", required=True, help="Anthropic model name")
    ap.add_argument(
        "--pin", type=float, required=True, help="USD per 1M input tokens"
    )
    ap.add_argument(
        "--pout", type=float, required=True, help="USD per 1M output tokens"
    )
    ap.add_argument(
        "--cap", type=float, default=10.0, help="Max USD to spend on judging"
    )
    ap.add_argument("--out", default="results/judge.csv")
    args = ap.parse_args()

    pool = pd.read_csv(args.pool)
    rows = []
    spent = 0.0

    for idx, row in pool.iterrows():
        # Read patch
        patch_path = Path(row.patch_path) if isinstance(row.patch_path, str) and row.patch_path else None
        patch = patch_path.read_text() if patch_path and patch_path.exists() else ""

        if not patch.strip():
            rows.append(dict(
                trial=row.trial,
                task=row.task,
                score=0.0,
                cost_usd=0.0,
                latency_s=0.0,
            ))
            continue

        # Read task instruction
        instruction = (Path(args.tasks) / row.task / "instruction.md").read_text()

        score, cost, latency = judge_score(
            instruction, patch, args.model, args.pin, args.pout
        )
        spent += cost

        rows.append(dict(
            trial=row.trial,
            task=row.task,
            score=score,
            cost_usd=cost,
            latency_s=latency,
        ))

        print(f"  [{idx+1}/{len(pool)}] {row.trial}: score={score:.1f} cost=${cost:.4f}")

        if spent > args.cap:
            print(f"JUDGE CAP HIT: ${spent:.2f} > ${args.cap:.2f}", file=sys.stderr)
            break

    judge_df = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    judge_df.to_csv(args.out, index=False)
    print(f"\nJudged {len(rows)} patches, total ${spent:.2f}")
    print(f"Saved to {args.out}")


if __name__ == "__main__":
    main()
