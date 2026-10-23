# Agent Trajectories (Deliverable 5)

> **Overview:** Exported session logs and trajectory traces demonstrating prompt flow, tool calls, patch generation, error feedback, and selection decisions across inference strategies.

---

## 1. Trajectory Manifest

| File | Strategy | Task ID | Key Decision Points Captured | Status |
|---|---|---|---|---|
| [task_01_single_shot.json](file:///c:/Users/kurap/Desktop/code/test0/trajectories/task_01_single_shot.json) | Baseline Single-Shot | `task-01` | Initial context intake, prompt construction, single patch output | ✅ Redacted & Sanitized |
| [task_03_refinement_k2.json](file:///c:/Users/kurap/Desktop/code/test0/trajectories/task_03_refinement_k2.json) | Iterative Refinement ($k=2$) | `task-03` | Verifier failure feedback, error parsing, patch self-correction | ✅ Redacted & Sanitized |
| [task_05_consensus_selection.json](file:///c:/Users/kurap/Desktop/code/test0/trajectories/task_05_consensus_selection.json) | Consensus@N ($N=8$) | `task-05` | 8 parallel candidate generations, Jaccard AST matrix, medoid vote | ✅ Redacted & Sanitized |
| [task_08_llm_judge.json](file:///c:/Users/kurap/Desktop/code/test0/trajectories/task_08_llm_judge.json) | LLM Judge ($N=4$) | `task-08` | Rubric scoring, criteria weighting, candidate rank ordering | ✅ Redacted & Sanitized |
| [agent_session_transcript.md](file:///c:/Users/kurap/Desktop/code/test0/trajectories/agent_session_transcript.md) | Full Agent Session | Multi-task | End-to-end orchestration transcript with tool calls and timings | ✅ Redacted & Sanitized |

---

## 2. Redaction & Privacy Specifications

| Item | Redaction Policy | Substitution Pattern |
|---|---|---|
| **API Keys** | Fully stripped | `[REDACTED_API_KEY]` |
| **Auth Tokens** | Fully stripped | `[REDACTED_BEARER_TOKEN]` |
| **Absolute Local Paths** | Generalized to workspace root | `/workspace/<path>` |
| **System Identity** | Sanitized | `agent-runner-worker-<id>` |

---

## 3. Trajectory Data Schema

| Field | Type | Description |
|---|---|---|
| `task_id` | String | Target benchmark task identifier |
| `strategy` | String | Inference compute allocation arm |
| `turns` | Array | Sequential interaction steps (prompt, thought, tool_call, tool_output) |
| `metrics` | Object | Token usage, cost (USD), latency (ms), model calls |
| `final_patch` | String | Git unified diff produced by the trajectory |
| `verification` | Object | Hidden test outcome, exit code, test stdout summary |
