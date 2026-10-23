#!/usr/bin/env python3
"""Iterative refinement arm: feed test failures back to the agent.

Usage (standalone):
    python src/refine.py --task-dir deep-swe/tasks/<task> \\
                         --patch results/patches/<trial>.patch \\
                         --model claude-sonnet-4-20250514 \\
                         --max-rounds 3

This module is also imported by analyze.py for the synthetic path.
"""

import argparse
import json
import re
import time
from pathlib import Path


REFINE_PROMPT = """\
You are a senior software engineer fixing a patch that failed some tests.

## Task
{instruction}

## Current Patch
{patch}

## Test Failures
{failures}

Write an improved unified diff that fixes these failures while keeping
all correct behavior.  Output ONLY the diff, no explanation."""


def refine_once(
    instruction: str,
    patch: str,
    failures: str,
    model: str,
    price_in: float,
    price_out: float,
) -> dict:
    """One refinement round via the Anthropic API.

    Returns dict with keys: patch, cost_usd, latency_s, in_tokens, out_tokens.
    """
    import anthropic

    t0 = time.time()
    msg = anthropic.Anthropic().messages.create(
        model=model,
        max_tokens=8192,
        messages=[
            {
                "role": "user",
                "content": REFINE_PROMPT.format(
                    instruction=instruction[:12_000],
                    patch=patch[:30_000],
                    failures=failures[:8_000],
                ),
            }
        ],
    )
    latency = time.time() - t0

    new_patch = msg.content[0].text
    cost = (
        msg.usage.input_tokens * price_in / 1e6
        + msg.usage.output_tokens * price_out / 1e6
    )

    return dict(
        patch=new_patch,
        cost_usd=cost,
        latency_s=latency,
        in_tokens=msg.usage.input_tokens,
        out_tokens=msg.usage.output_tokens,
    )


def refine_loop(
    instruction: str,
    initial_patch: str,
    get_failures,  # callable(patch) -> str
    model: str,
    max_rounds: int = 3,
    price_in: float = 3.0,
    price_out: float = 15.0,
) -> list[dict]:
    """Run up to max_rounds of refinement, stopping early if tests pass.

    Parameters
    ----------
    get_failures : callable taking a patch string and returning test failure
                   output (empty string if all pass).

    Returns list of round records with cumulative cost.
    """
    rounds = []
    current_patch = initial_patch
    cumulative_cost = 0.0

    for k in range(1, max_rounds + 1):
        failures = get_failures(current_patch)
        if not failures.strip():
            # Tests pass—no more refinement needed
            rounds.append(
                dict(
                    round=k,
                    action="pass",
                    cost_usd=0.0,
                    cumulative_cost_usd=cumulative_cost,
                    latency_s=0.0,
                )
            )
            break

        result = refine_once(
            instruction, current_patch, failures, model, price_in, price_out
        )
        cumulative_cost += result["cost_usd"]
        current_patch = result["patch"]
        rounds.append(
            dict(
                round=k,
                action="refine",
                cost_usd=result["cost_usd"],
                cumulative_cost_usd=cumulative_cost,
                latency_s=result["latency_s"],
            )
        )

    return rounds


# ── Synthetic refinement for pipeline validation ───────────


def simulate_refine(
    base_pass_rate: float,
    k: int,
    rng=None,
    base_cost: float = 0.75,
    cost_per_round: float = 0.35,
) -> dict:
    """Simulate refinement outcome for pipeline validation.

    Each round has diminishing probability of fixing a failing patch.
    """
    import random as _rnd

    rng = rng or _rnd
    passed = rng.random() < base_pass_rate
    total_cost = base_cost

    if not passed:
        for r in range(k):
            # Diminishing returns: each round has decreasing fix probability
            fix_prob = 0.25 / (r + 1)
            total_cost += cost_per_round
            if rng.random() < fix_prob:
                passed = True
                break

    return dict(
        passed=int(passed),
        cost_usd=round(total_cost, 4),
        rounds_used=min(k, k),
        latency_s=round(45 + k * 30 + rng.gauss(0, 5), 1),
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-dir", type=Path, required=True)
    ap.add_argument("--patch", type=Path, required=True)
    ap.add_argument("--model", default="claude-sonnet-4-20250514")
    ap.add_argument("--max-rounds", type=int, default=3)
    ap.add_argument("--pin", type=float, default=3.0, help="$/1M input tokens")
    ap.add_argument(
        "--pout", type=float, default=15.0, help="$/1M output tokens"
    )
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    instruction = (args.task_dir / "instruction.md").read_text()
    patch = args.patch.read_text()

    print(f"Refining {args.patch.name} for up to {args.max_rounds} rounds...")
    print("(Requires test runner integration—see README for setup)")
