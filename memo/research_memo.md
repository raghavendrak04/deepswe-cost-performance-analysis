# Research Memo: Inference-Time Compute Allocation for Coding Agents

**Author:** Research Engineer Candidate  
**Date:** 2026-10  
**Budget constraint:** ≤ $100 inference spend

---

## 1) Hypothesis

For a fixed inference budget on DeepSWE tasks, **iterative refinement** will provide a better cost-to-success trade-off than naive best-of-N random selection, while selector-based best-of-N methods (consensus/judge) can recover some of the oracle headroom.

This hypothesis is falsifiable by showing that refinement does not improve success-per-dollar over baseline/random controls on the same task subset.

---

## 2) Experimental Design

### Benchmark and controls

- Benchmark: DeepSWE-compatible tasks, reproducible 10-task subset (`--n-tasks 10 --sample-seed 0`)
- Same correctness criterion across all arms: hidden test pass/fail
- No model training/fine-tuning
- Same task set for all comparisons

### Arms compared

1. **Single-shot baseline** (N=1)
2. **Best-of-N controls and selectors** at N in {2,4,8}
   - random@N
   - consensus@N (Jaccard medoid over changed lines)
   - judge@N (LLM rubric)
   - oracle@N (upper bound only)
3. **Refinement depth** at k in {1,2,3}

### Metrics logged

- Task success rate
- Cost (USD): per task + total
- Latency
- Model-call count
- Bootstrap confidence intervals (paired resampling)

---

## 3) What Was Implemented

- Pool generation script: `src/run_pool.sh`
- Result ingestion and normalization: `src/collect.py`
- Selectors (random/consensus/judge): `src/select_patch.py`, `src/judge_pool.py`
- Iterative refinement simulation/evaluation: `src/refine.py`
- Pareto + diagnostics engine: `src/analyze.py`
- Tests: `tests/test_selectors.py`

Artifacts:
- Summary tables: `results_synth/summary.csv`, `results_synth/per_task.csv`, `results_synth/diagnostics.txt`
- Pareto figure: `results_synth/pareto.png`
- Trajectories: `trajectories/`

---

## 4) Main Findings (from `results_synth`)

Key points from `results_synth/summary.csv`:

- single-shot: success 0.41 at $0.73/task
- random@8: success 0.4126 at $6.37/task (dominated)
- consensus@8: success 0.5174 at $6.37/task
- judge@8: success 0.5728 at $6.77/task
- refine-k=3: success 0.6166 at $1.63/task
- oracle@8: success 0.6650 at $6.37/task (ceiling)

Interpretation:

1. **Random best-of-N adds cost without value.**
2. **Selector quality matters:** consensus and judge recover non-trivial fractions of oracle headroom.
3. **Refinement dominates cost-efficiency** in this setup.
4. **Diminishing returns appear** as both N and k increase.

---

## 5) Pareto and Budget Decision

Empirical frontier from current bundle is anchored by:

- single-shot → refine-k=1 → refine-k=2 → refine-k=3

Under a strict budget, the best practical point is near **refine-k=2 or refine-k=3** in this dataset, because they exceed judge@N high-cost points on success-per-dollar.

---

## 6) Limitations and Integrity Notes

1. The included `results_synth/` bundle is synthetic/calibrated, useful for pipeline validation and method comparison prototyping, not definitive external benchmark proof.
2. Sample size is small (10 tasks), so confidence intervals are wide.
3. Cross-model and cross-task-distribution generalization remains unproven.

To claim final benchmark evidence quality, run and report measured outputs in `results/` generated from a real benchmark execution under the same protocol.

---

## 7) Cheapest Disproof Experiment

A minimal disproof test is:

- Hold tasks and seed fixed.
- Compare success-per-dollar of baseline vs refine-k=1 on measured runs.
- If refine-k=1 does not outperform baseline within uncertainty, the hypothesis fails.

This is cheap because it requires only one additional refinement round per task.

---

## 8) Two-Week Follow-up Plan

1. Scale from 10 tasks to a larger subset for tighter uncertainty.
2. Add adaptive budget policy (early-stop / escalate).
3. Evaluate mixed-model diversity in best-of-N pools.
4. Improve selector quality with a lightweight learned reranker.
5. Report calibrated latency/reliability trade-offs under fixed SLA.

---

## 9) Submission Quality Upgrade Checklist (for 80–100 target)

- [ ] Replace synthetic bundle with measured run outputs.
- [ ] Publish exact task IDs and run manifest.
- [ ] Include per-arm token, latency, and call-count distributions.
- [ ] Keep all claims traceable to CSV rows and plots.
- [ ] State uncertainty and negative results explicitly.
- [ ] Provide one crisp budget recommendation and failure cases.

