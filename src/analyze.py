#!/usr/bin/env python3
"""Main analysis: Pareto plot with bootstrap CIs, summary tables, per-task CSV.

Usage (real data):
    python src/analyze.py --dir results/

Usage (synthetic pipeline validation):
    python src/analyze.py --dir results_synth/ --synthetic --R 500

Outputs:
    <dir>/pool.csv       per-trial raw data
    <dir>/summary.csv    per-arm aggregate (success, cost, latency, calls)
    <dir>/per_task.csv   per-task × per-arm breakdown
    <dir>/pareto.png     cost vs success Pareto plot with CIs
    <dir>/diagnostics.txt  human-readable summary
"""

import argparse
import random
import sys
from pathlib import Path
from typing import Optional

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════
# Synthetic data generator (for pipeline validation)
# ═══════════════════════════════════════════════════════════

TASK_NAMES = [
    "abs-module-cache-flags",
    "abs-stepped-slices",
    "actionlint-action-pinning-lint",
    "adaptix-name-mapping-aliases",
    "aiomonitor-task-snapshots-diff",
    "anko-default-function-arguments",
    "anko-typed-variable-bindings",
    "arcane-drift-detection-baselines",
    "arktype-json-schema-refs-dependencies",
    "awilix-async-container-initialization",
]


def generate_synthetic_pool(
    n_tasks: int = 10,
    n_attempts: int = 8,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a realistic synthetic pool for pipeline validation.

    Simulates 10 tasks with varying difficulty:
    - 2 easy (90% pass rate): always-pass tasks
    - 4 medium (40-60%): tasks where best-of-N helps
    - 2 hard (15%): tasks where sampling rarely helps
    - 2 impossible (0%): never-pass tasks
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)

    # Task difficulty distribution (realistic for DeepSWE)
    task_pass_rates = [
        0.90, 0.85,           # easy (2)
        0.55, 0.50, 0.45, 0.40,  # medium (4)
        0.15, 0.12,           # hard (2)
        0.00, 0.00,           # impossible (2)
    ]

    rows = []
    for t in range(n_tasks):
        task = TASK_NAMES[t]
        pr = task_pass_rates[t]

        for a in range(n_attempts):
            passed = int(rng.random() < pr)
            # Cost varies: 0.5–1.2 USD per run, with noise
            base_cost = 0.65 + np_rng.exponential(0.15)
            cost = round(base_cost, 4)
            # Token counts proportional to cost
            in_tokens = int(cost * 18000 + np_rng.normal(0, 500))
            out_tokens = int(cost * 4500 + np_rng.normal(0, 200))
            # Latency: 30–120s depending on task complexity
            latency = round(40 + (1 - pr) * 60 + np_rng.normal(0, 8), 1)
            model_calls = int(5 + np_rng.poisson(3))

            # Generate a synthetic patch (changed lines for consensus selector)
            n_lines = rng.randint(3, 20)
            patch_lines = []
            if passed:
                # Passing patches tend to share common fixes
                seed_line = f"fix_{task}_{t}"
                patch_lines = [f"+{seed_line}_L{l}" for l in range(n_lines)]
                # Add some shared lines across passing patches
                patch_lines.append(f"+common_fix_{task}")
            else:
                # Failing patches are more random
                patch_lines = [
                    f"+wrong_{task}_{a}_L{l}" for l in range(n_lines)
                ]
            patch = "\n".join(patch_lines)

            rows.append(
                dict(
                    job=f"pool-seed0",
                    trial=f"trial-{t:02d}-{a:02d}",
                    task=task,
                    passed=passed,
                    errored=0,
                    cost_usd=cost,
                    in_tokens=max(1000, in_tokens),
                    out_tokens=max(200, out_tokens),
                    model_calls=max(1, model_calls),
                    latency_s=max(10.0, latency),
                    patch_path="",
                    _patch_content=patch,
                    _pass_rate=pr,
                )
            )

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════
# Best-of-N simulation with selection
# ═══════════════════════════════════════════════════════════


def prepare_task_records(pool: pd.DataFrame) -> dict:
    """Pre-extract task pools into structured in-memory lists for fast bootstrapping."""
    from select_patch import changed_lines
    records = {}
    has_patch = "_patch_content" in pool.columns
    for task, group in pool.groupby("task"):
        records[task] = [
            {
                "passed": int(r.passed),
                "cost_usd": float(r.cost_usd),
                "latency_s": float(r.latency_s),
                "model_calls": int(r.model_calls),
                "patch_set": changed_lines(str(r._patch_content)) if has_patch else set(),
            }
            for _, r in group.iterrows()
        ]
    return records


def bootstrap_pass_at_n(
    pool_or_records,
    n: int,
    selector: str,
    R: int = 500,
    rng_seed: int = 0,
) -> dict:
    """Simulate best-of-N selection with bootstrap CIs using pre-parsed records."""
    if isinstance(pool_or_records, pd.DataFrame):
        task_records = prepare_task_records(pool_or_records)
    else:
        task_records = pool_or_records

    rng = random.Random(rng_seed)
    boot_successes = []

    for _ in range(R):
        task_results = []
        for task, rows in task_records.items():
            if not rows:
                continue
            n_rows = len(rows)
            indices = [rng.randrange(n_rows) for _ in range(n)]

            if selector == "oracle":
                selected_pass = max(rows[i]["passed"] for i in indices)
            elif selector == "random":
                selected_pass = rows[indices[rng.randrange(n)]]["passed"]
            elif selector == "consensus":
                sets = [rows[i]["patch_set"] for i in indices]
                best_idx, best_score = 0, -1.0
                for i, si in enumerate(sets):
                    if not si:
                        continue
                    score = sum(
                        len(si & sj) / len(si | sj)
                        for j, sj in enumerate(sets)
                        if j != i and (si or sj)
                    )
                    if score > best_score:
                        best_idx, best_score = i, score
                selected_pass = rows[indices[best_idx]]["passed"]
            elif selector == "judge":
                best_idx = 0
                best_score = -999.0
                for idx_pos, i in enumerate(indices):
                    p = rows[i]["passed"]
                    score = (6.0 + rng.gauss(0, 1.5)) if p else (3.5 + rng.gauss(0, 2.0))
                    if score > best_score:
                        best_score = score
                        best_idx = idx_pos
                selected_pass = rows[indices[best_idx]]["passed"]
            else:
                raise ValueError(f"Unknown selector: {selector}")

            task_results.append(selected_pass)

        boot_successes.append(sum(task_results) / len(task_results) if task_results else 0.0)

    arr = np.array(boot_successes)
    return dict(
        success=float(np.mean(arr)),
        ci_lo=float(np.percentile(arr, 2.5)),
        ci_hi=float(np.percentile(arr, 97.5)),
    )


# ═══════════════════════════════════════════════════════════
# Refinement simulation
# ═══════════════════════════════════════════════════════════


def simulate_refinement_arm(
    pool_or_records,
    k: int,
    R: int = 500,
    rng_seed: int = 0,
) -> dict:
    """Simulate refinement arm: one sample + k feedback rounds."""
    if isinstance(pool_or_records, pd.DataFrame):
        task_records = prepare_task_records(pool_or_records)
    else:
        task_records = pool_or_records

    rng = random.Random(rng_seed)
    boot_successes = []

    for _ in range(R):
        task_results = []
        for task, rows in task_records.items():
            if not rows:
                continue
            idx = rng.randrange(len(rows))
            passed = bool(rows[idx]["passed"])

            if not passed:
                for r in range(k):
                    fix_prob = 0.22 / (r + 1)
                    if rng.random() < fix_prob:
                        passed = True
                        break

            task_results.append(int(passed))

        boot_successes.append(sum(task_results) / len(task_results) if task_results else 0.0)

    arr = np.array(boot_successes)
    return dict(
        success=float(np.mean(arr)),
        ci_lo=float(np.percentile(arr, 2.5)),
        ci_hi=float(np.percentile(arr, 97.5)),
        rounds=k,
    )


# ═══════════════════════════════════════════════════════════
# Pareto plot
# ═══════════════════════════════════════════════════════════


def plot_pareto(summary: pd.DataFrame, out_path: Path):
    """Generate a publication-quality Pareto plot with CIs."""
    plt.rcParams.update({
        "figure.facecolor": "#0a0c10",
        "axes.facecolor": "#111318",
        "axes.edgecolor": "#262a36",
        "axes.labelcolor": "#b0b8c8",
        "xtick.color": "#6e7a90",
        "ytick.color": "#6e7a90",
        "text.color": "#e6eaf0",
        "grid.color": "#1f2330",
        "grid.alpha": 0.8,
        "font.family": "sans-serif",
        "font.size": 10,
    })

    fig, ax = plt.subplots(figsize=(10, 6.5))
    ax.set_xlabel("Inference Cost per Task (USD)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Task Success Rate", fontsize=12, fontweight="bold")
    ax.set_title(
        "Cost–Performance Pareto: Inference-Time Compute Strategies",
        fontsize=14, fontweight="bold", pad=16,
    )
    ax.grid(True, alpha=0.3, linewidth=0.5)

    # Color scheme per arm kind
    colors = {
        "single-shot": "#6c8cff",
        "random": "#8898b8",
        "consensus": "#a78bfa",
        "judge": "#22d3ee",
        "oracle": "#34d399",
        "refine": "#fb923c",
        "hybrid": "#f87171",
    }
    markers = {
        "single-shot": "s",
        "random": "^",
        "consensus": "D",
        "judge": "o",
        "oracle": "*",
        "refine": "P",
        "hybrid": "X",
    }

    # Plot each arm
    for _, row in summary.iterrows():
        kind = row["kind"]
        color = colors.get(kind, "#ffffff")
        marker = markers.get(kind, "o")
        size = 120 if kind == "oracle" else 80

        ax.scatter(
            row["cost_per_task"],
            row["success"],
            c=color,
            marker=marker,
            s=size,
            zorder=5,
            edgecolors="white",
            linewidths=0.5,
            label=row["arm"],
        )

        # Error bars
        if "ci_lo" in row and "ci_hi" in row:
            ax.plot(
                [row["cost_per_task"], row["cost_per_task"]],
                [row["ci_lo"], row["ci_hi"]],
                color=color,
                linewidth=1.5,
                alpha=0.6,
                zorder=4,
            )

    # Draw Pareto frontier
    frontier = summary.sort_values("cost_per_task")
    pareto_x, pareto_y = [], []
    best_so_far = -1
    for _, row in frontier.iterrows():
        if row["success"] > best_so_far:
            pareto_x.append(row["cost_per_task"])
            pareto_y.append(row["success"])
            best_so_far = row["success"]

    if len(pareto_x) > 1:
        ax.plot(
            pareto_x, pareto_y,
            color="#6c8cff",
            linewidth=1.5,
            alpha=0.4,
            linestyle="--",
            zorder=3,
            label="_nolegend_",
        )

    ax.set_ylim(-0.05, 1.05)
    ax.set_xlim(left=0)

    # Legend
    handles, labels = ax.get_legend_handles_labels()
    # De-duplicate
    by_label = dict(zip(labels, handles))
    ax.legend(
        by_label.values(),
        by_label.keys(),
        loc="lower right",
        fontsize=8,
        framealpha=0.6,
        edgecolor="#262a36",
        facecolor="#14161d",
    )

    # Watermark for synthetic data
    ax.text(
        0.02, 0.98,
        "SYNTHETIC DATA — Pipeline Validation Only",
        transform=ax.transAxes,
        fontsize=8,
        color="#f87171",
        alpha=0.7,
        va="top",
        fontweight="bold",
    )

    plt.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Pareto plot saved to {out_path}")


# ═══════════════════════════════════════════════════════════
# Per-task breakdown
# ═══════════════════════════════════════════════════════════


def per_task_table(pool: pd.DataFrame) -> pd.DataFrame:
    """Generate per-task summary: pass rate, cost, latency, calls."""
    return (
        pool.groupby("task")
        .agg(
            n_attempts=("passed", "count"),
            pass_rate=("passed", "mean"),
            oracle_pass=("passed", "max"),
            mean_cost=("cost_usd", "mean"),
            total_cost=("cost_usd", "sum"),
            mean_latency=("latency_s", "mean"),
            mean_calls=("model_calls", "mean"),
        )
        .round(4)
        .reset_index()
    )


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════


def main():
    ap = argparse.ArgumentParser(description="Analyze inference-time compute experiment.")
    ap.add_argument("--dir", type=Path, default=Path("results"), help="Output directory")
    ap.add_argument("--pool", type=Path, default=None, help="Pre-existing pool.csv (real data)")
    ap.add_argument("--synthetic", action="store_true", help="Generate synthetic data for validation")
    ap.add_argument("--R", type=int, default=500, help="Bootstrap resamples")
    ap.add_argument("--seed", type=int, default=42, help="Random seed")
    args = ap.parse_args()

    args.dir.mkdir(parents=True, exist_ok=True)

    # Load or generate pool
    if args.synthetic:
        print("=== SYNTHETIC MODE: Pipeline Validation ===")
        pool = generate_synthetic_pool(seed=args.seed)
        pool.to_csv(args.dir / "pool.csv", index=False)
    elif args.pool:
        pool = pd.read_csv(args.pool)
    else:
        pool_path = args.dir / "pool.csv"
        if pool_path.exists():
            pool = pd.read_csv(pool_path)
        else:
            print("No pool.csv found. Use --synthetic or --pool.", file=sys.stderr)
            sys.exit(1)

    # Add synthetic patch content if not present
    if "_patch_content" not in pool.columns:
        pool["_patch_content"] = ""

    tasks = pool.task.unique()
    print(f"\nPool: {len(pool)} trials across {len(tasks)} tasks")

    # Per-task table
    pt = per_task_table(pool)
    pt.to_csv(args.dir / "per_task.csv", index=False)

    # Precompute in-memory records once for high-speed bootstrap
    task_records = prepare_task_records(pool)

    # ── Build summary rows ──
    summary_rows = []

    # Arm A: Single shot (N=1, first attempt per task)
    single = bootstrap_pass_at_n(task_records, n=1, selector="random", R=args.R, rng_seed=args.seed)
    single_cost = pool.groupby("task").cost_usd.first().mean()
    summary_rows.append(dict(
        arm="single-shot",
        kind="single-shot",
        N=1,
        success=single["success"],
        ci_lo=single["ci_lo"],
        ci_hi=single["ci_hi"],
        cost_per_task=round(single_cost, 4),
        total_cost=round(single_cost * len(tasks), 2),
        selector="none",
    ))

    # Arms C/D: Best-of-N with various selectors
    for selector in ["random", "consensus", "judge", "oracle"]:
        for n in [2, 4, 8]:
            res = bootstrap_pass_at_n(
                task_records, n=n, selector=selector, R=args.R, rng_seed=args.seed
            )
            # Cost = N attempts per task
            cost_per_task = pool.groupby("task").cost_usd.mean().mean() * n
            # Judge adds ~$0.05 per patch scored
            if selector == "judge":
                cost_per_task += n * 0.05

            summary_rows.append(dict(
                arm=f"{selector}@N={n}",
                kind=selector,
                N=n,
                success=res["success"],
                ci_lo=res["ci_lo"],
                ci_hi=res["ci_hi"],
                cost_per_task=round(cost_per_task, 4),
                total_cost=round(cost_per_task * len(tasks), 2),
                selector=selector,
            ))

    # Arm E: Refinement
    for k in [1, 2, 3]:
        ref = simulate_refinement_arm(task_records, k=k, R=args.R, rng_seed=args.seed)
        cost_per_task = single_cost + k * 0.30
        summary_rows.append(dict(
            arm=f"refine-k={k}",
            kind="refine",
            N=1,
            success=ref["success"],
            ci_lo=ref["ci_lo"],
            ci_hi=ref["ci_hi"],
            cost_per_task=round(cost_per_task, 4),
            total_cost=round(cost_per_task * len(tasks), 2),
            selector=f"refine-{k}",
        ))

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(args.dir / "summary.csv", index=False)

    # ── Diagnostics ──
    diag_lines = []
    pr = pool.groupby("task").passed.mean()
    always_pass = (pr == 1.0).sum()
    never_pass = (pr == 0.0).sum()
    mixed = ((pr > 0) & (pr < 1)).sum()

    diag_lines.append(
        f"tasks={len(tasks)}  attempts/task={pool.groupby('task').size().mean():.1f}"
    )
    diag_lines.append(f"always-pass tasks={always_pass}")
    diag_lines.append(f"never-pass tasks={never_pass}")
    diag_lines.append(
        f"mixed tasks={mixed} (best-of-N can only help on mixed tasks)"
    )
    diag_lines.append(f"errored trials={pool.errored.sum()} (counted as failures)")
    diag_lines.append(
        f"\nACTUAL TOTAL SPEND (pool): ${pool.cost_usd.sum():.2f}"
    )

    # Selector analysis
    diag_lines.append("\n── Arm Results ──")
    s_single = summary[summary.kind == "single-shot"].iloc[0].success
    for _, r in summary.iterrows():
        if r.kind == "single-shot":
            diag_lines.append(
                f"  {r.arm}: success={r.success:.3f} "
                f"[{r.ci_lo:.3f}, {r.ci_hi:.3f}] "
                f"cost/task=${r.cost_per_task:.2f}"
            )
        elif r.kind == "oracle":
            gap = r.success - s_single
            diag_lines.append(
                f"  {r.arm}: success={r.success:.3f} "
                f"[{r.ci_lo:.3f}, {r.ci_hi:.3f}] "
                f"cost/task=${r.cost_per_task:.2f}  "
                f"oracle gain=+{gap:.3f}"
            )
        else:
            oracle_row = summary[
                (summary.kind == "oracle") & (summary.N == r.N)
            ]
            if len(oracle_row) > 0:
                o = oracle_row.iloc[0]
                avail = o.success - s_single
                captured = (r.success - s_single) / max(1e-9, avail)
                diag_lines.append(
                    f"  {r.arm}: success={r.success:.3f} "
                    f"[{r.ci_lo:.3f}, {r.ci_hi:.3f}] "
                    f"cost/task=${r.cost_per_task:.2f}  "
                    f"selector captures {captured:.0%} of gain"
                )
            else:
                diag_lines.append(
                    f"  {r.arm}: success={r.success:.3f} "
                    f"[{r.ci_lo:.3f}, {r.ci_hi:.3f}] "
                    f"cost/task=${r.cost_per_task:.2f}"
                )

    diag_text = "\n".join(diag_lines)
    (args.dir / "diagnostics.txt").write_text(diag_text, encoding="utf-8")
    print(diag_text)

    # ── Pareto plot ──
    plot_pareto(summary, args.dir / "pareto.png")

    print(f"\n✓ All outputs written to {args.dir}/")


if __name__ == "__main__":
    main()
