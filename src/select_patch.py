#!/usr/bin/env python3
"""Patch selectors: choose one patch from a pool WITHOUT seeing hidden tests.

Selectors
---------
- random:    baseline, picks uniformly at random
- consensus: medoid by Jaccard similarity of changed lines (zero API cost)
- judge:     LLM scores each patch vs. the task instruction (costs API calls)
"""

import random
import re


# ── Utilities ──────────────────────────────────────────────


def changed_lines(patch: str) -> set[str]:
    """Extract added/removed lines from a unified diff, ignoring file headers."""
    return {
        line[1:].strip()
        for line in patch.splitlines()
        if line[:1] in "+-"
        and not line.startswith(("+++", "---"))
        and line[1:].strip()
    }


def jaccard(a: set, b: set) -> float:
    """Jaccard similarity of two sets."""
    union = a | b
    return len(a & b) / len(union) if union else 0.0


# ── Selectors ──────────────────────────────────────────────


def pick_random(n: int, rng: random.Random | None = None) -> int:
    """Return a random index in [0, n)."""
    return (rng or random).randrange(n)


def pick_consensus(patches: list[str]) -> int:
    """Pick the medoid patch by Jaccard similarity of changed lines.

    The medoid is the patch whose diff overlaps most with all others.
    Empty patches always lose unless every patch is empty.
    """
    sets = [changed_lines(p) for p in patches]
    best_idx, best_score = 0, -1.0

    for i, si in enumerate(sets):
        if not si:
            continue
        score = sum(jaccard(si, sj) for j, sj in enumerate(sets) if j != i)
        if score > best_score:
            best_idx, best_score = i, score

    return best_idx


# ── LLM Judge ──────────────────────────────────────────────

JUDGE_PROMPT = """\
You review a candidate patch for a software task.

Task:
{instruction}

Patch:
{patch}

Rate from 0 to 10 how likely this patch fully implements the task and
passes hidden behavioural tests.  Consider missing requirements, edge
cases, and unrelated changes.

Reply with ONLY:  SCORE: <number>"""


def judge_score(
    instruction: str,
    patch: str,
    model: str,
    price_in: float,
    price_out: float,
) -> tuple[float, float, float]:
    """Score a patch with an LLM judge.

    Parameters
    ----------
    instruction : task description (will be truncated to 12 000 chars)
    patch       : unified diff (truncated to 60 000 chars)
    model       : Anthropic model name
    price_in    : USD per 1 M input tokens
    price_out   : USD per 1 M output tokens

    Returns
    -------
    (score, cost_usd, latency_s)
    """
    import time

    import anthropic

    t0 = time.time()
    msg = anthropic.Anthropic().messages.create(
        model=model,
        max_tokens=50,
        messages=[
            {
                "role": "user",
                "content": JUDGE_PROMPT.format(
                    instruction=instruction[:12_000],
                    patch=patch[:60_000],
                ),
            }
        ],
    )
    latency = time.time() - t0

    text = msg.content[0].text
    match = re.search(r"SCORE:\s*([0-9.]+)", text)
    score = float(match.group(1)) if match else 0.0

    cost = (
        msg.usage.input_tokens * price_in / 1e6
        + msg.usage.output_tokens * price_out / 1e6
    )

    return score, cost, latency
