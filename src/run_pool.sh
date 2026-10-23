#!/usr/bin/env bash
# run_pool.sh — Generate N agent attempts per task via Pier
#
# Usage:
#   ./src/run_pool.sh [N_ATTEMPTS] [TASKS_DIR] [MODEL] [JOB_NAME]
#
# Environment:
#   ANTHROPIC_API_KEY  must be set
#   PIER_ENV           "docker" (default) or "modal"
#
# Prerequisites:
#   uv tool install datacurve-pier
#   git clone https://github.com/datacurve-ai/deep-swe

set -euo pipefail

N=${1:-8}
TASKS=${2:-deep-swe/tasks}
MODEL=${3:-claude-sonnet-4-20250514}
JOB=${4:-pool-seed0}
ENV=${PIER_ENV:-docker}
SUBSET_ARGS="--n-tasks 10 --sample-seed 0"

echo "═══════════════════════════════════════════"
echo " Inference-Time Compute Pool Generation"
echo "═══════════════════════════════════════════"
echo " Tasks dir : $TASKS"
echo " Model     : $MODEL"
echo " Attempts  : $N per task (10 tasks = $((N * 10)) total)"
echo " Job name  : $JOB"
echo " Env       : $ENV"
echo "═══════════════════════════════════════════"

# Pre-flight: API key check
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ERROR: ANTHROPIC_API_KEY not set" >&2
  exit 1
fi

# Pilot: Run ONE task first to get cost estimate
echo ""
echo "── Step 1: Pilot (1 task, 1 attempt) ──"
pier run \
  -p "$TASKS" \
  -a claude-code \
  -m "$MODEL" \
  --env "$ENV" \
  $SUBSET_ARGS \
  --n-tasks 1 \
  -k 1 \
  --job-name "${JOB}-pilot" \
  2>&1 | tee /tmp/pilot.log

echo ""
echo "── Pilot complete. Check cost above. ──"
echo "── Press Enter to continue with full pool, or Ctrl+C to abort ──"
read -r

# Full pool: N attempts per task
echo ""
echo "── Step 2: Full Pool ($N attempts × 10 tasks) ──"
pier run \
  -p "$TASKS" \
  -a claude-code \
  -m "$MODEL" \
  --env "$ENV" \
  $SUBSET_ARGS \
  -k "$N" \
  --job-name "$JOB" \
  2>&1 | tee /tmp/pool.log

echo ""
echo "── Pool generation complete ──"
echo "── Run: python src/collect.py pier-jobs/ --out results/pool.csv --cap 60 ──"
