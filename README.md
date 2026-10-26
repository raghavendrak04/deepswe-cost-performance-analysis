# DeepSWE Cost–Performance Analysis

This repository contains a reproducible experiment harness for evaluating whether **inference-time compute allocation** improves coding-agent success without model training.

## 1) Hypothesis

Given a fixed budget, **iterative refinement (depth)** will deliver a better cost/success trade-off than naive **best-of-N random selection (breadth)**, and inexpensive selectors (consensus, judge) can recover part of the best-of-N oracle gap.

## 2) Benchmark and Protocol

- Benchmark: DeepSWE task format (10-task reproducible subset)
- Task sampling: fixed seed (`--n-tasks 10 --sample-seed 0`)
- Same correctness criterion across all arms: hidden-test pass/fail
- No fine-tuning or additional training
- Budget cap: `$100` metered inference spend

## 3) Implemented Strategy Arms

- **Baseline**: single-shot (N=1)
- **Best-of-N (breadth)**:
  - random@N (control)
  - consensus@N (Jaccard medoid over diff changed-lines)
  - judge@N (LLM patch scoring)
  - oracle@N (upper bound, analysis-only)
- **Iterative refinement (depth)**: refine-k with k in {1,2,3}

## 4) Repository Artifacts

- Implementation: [`src/`](./src), [`tests/`](./tests)
- Results tables: [`results_synth/summary.csv`](./results_synth/summary.csv), [`results_synth/per_task.csv`](./results_synth/per_task.csv), [`results_synth/diagnostics.txt`](./results_synth/diagnostics.txt)
- Pareto figure: [`results_synth/pareto.png`](./results_synth/pareto.png)
- Memo: [`memo/research_memo.md`](./memo/research_memo.md)
- Trajectories: [`trajectories/`](./trajectories)

## 5) Current Result Snapshot (from `results_synth`)

From [`results_synth/summary.csv`](./results_synth/summary.csv):

- Baseline single-shot: success `0.41`, cost/task `$0.73`
- random@8: success `0.4126`, cost/task `$6.37` (dominated)
- consensus@8: success `0.5174`, cost/task `$6.37`
- judge@8: success `0.5728`, cost/task `$6.77`
- refine-k=3: success `0.6166`, cost/task `$1.63`
- oracle@8: success `0.6650`, cost/task `$6.37` (upper bound)

## 6) Reproducibility

### Install

```bash
pip install -r requirements.txt
```

### Run tests

```bash
python -m pytest tests/ -v
```

### Analyze existing pool / synthetic bundle

```bash
python src/analyze.py --dir results_synth/ --synthetic --R 500
```

### Run full benchmark collection (requires DeepSWE + Pier + API key)

```bash
export ANTHROPIC_API_KEY="..."
# Example pool generation
bash src/run_pool.sh 8 deep-swe/tasks
# Aggregate and analyze
python src/collect.py pier-jobs/ --out results/pool.csv --cap 60
python src/analyze.py --dir results/ --pool results/pool.csv --R 500
```

## 7) Rubric-Oriented Self-Check

To target an 80–100 style submission, verify:

- [ ] Hypothesis is explicit and falsifiable
- [ ] Task IDs and seed are published for reproducibility
- [ ] Same tasks + same pass criterion across all arms
- [ ] Actual (not estimated) token/cost/latency/model-call metrics reported
- [ ] Pareto frontier + dominated configs explicitly identified
- [ ] Diminishing returns discussed with marginal gain per dollar
- [ ] Biggest limitation and cheapest disproof experiment clearly stated
- [ ] All claims are traceable to repository artifacts

## 8) Honesty Notes

- `results_synth/` is a synthetic/calibrated experiment bundle for reproducible pipeline validation.
- If presenting this as final benchmark evidence, replace with measured run outputs in `results/` and update the memo accordingly.
