# Agent Trajectories (Deliverable 5)

Exported trajectory artifacts showing prompts, tool use, candidate patches, and decision points across strategy arms.

## Trajectory Manifest

| File | Strategy | Task ID | Key Decision Points | Status |
|---|---|---|---|---|
| [`task_01_single_shot.json`](./task_01_single_shot.json) | Baseline single-shot | `task-01` | Initial context, prompt, first patch output | ✅ Redacted |
| [`task_03_refinement_k2.json`](./task_03_refinement_k2.json) | Iterative refinement (`k=2`) | `task-03` | Failure feedback parsing and correction loop | ✅ Redacted |
| [`task_05_consensus_selection.json`](./task_05_consensus_selection.json) | Consensus@8 | `task-05` | 8 candidates, overlap scoring, medoid pick | ✅ Redacted |
| [`task_08_llm_judge.json`](./task_08_llm_judge.json) | LLM judge@4 | `task-08` | Rubric scoring and ranking | ✅ Redacted |
| [`agent_session_transcript.md`](./agent_session_transcript.md) | Full session log | multi-task | End-to-end orchestration and tool timeline | ✅ Redacted |

## Redaction Policy

| Item | Policy | Replacement |
|---|---|---|
| API keys | removed | `[REDACTED_API_KEY]` |
| Auth tokens | removed | `[REDACTED_BEARER_TOKEN]` |
| Absolute paths | normalized | `/workspace/<path>` |
| Host identity | sanitized | `agent-runner-worker-<id>` |

## Data Schema

| Field | Type | Meaning |
|---|---|---|
| `task_id` | string | benchmark task identifier |
| `strategy` | string | inference strategy arm |
| `turns` | array | ordered prompt/tool/action trace |
| `metrics` | object | tokens, cost, latency, model calls |
| `final_patch` | string | produced unified diff |
| `verification` | object | verifier outcome summary |
