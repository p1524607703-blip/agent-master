# DeepSeek Harness GPT MCP Bridge

This external DeepSeek Harness bundle exposes the running Web profile to ChatGPT through a local Streamable HTTP MCP endpoint.

## Architecture (0.5.0)

`Current ChatGPT ↔ Tunnel External Model Driver ↔ native DSH Agent Loop ↔ DSH Tools`

The bridge is a task-control adapter, **not a second model/tool loop**. DSH owns the loop, tool execution, permissions and durable session journal. The current ChatGPT session makes each model decision through `agent_model_request` / `agent_model_respond`; no DeepSeek or OpenAI model API is called by this Web profile. One decision may contain multiple tool calls, but a later decision after observing their results still requires ChatGPT.

In the default `agent-loop` mode, ChatGPT receives task control plus read-only session/trajectory/model tools. Direct filesystem, shell, process and Git tools, and unowned session mutation, are not registered. DSH itself retains the deployment's existing `danger-full-access` / `never` posture; this is **not a filesystem sandbox**. Only submit trusted tasks within their authorized scope.

The previous `harness_run` already called DSH's native prompt API. This upgrade makes that delegation the default and adds a durable, asynchronous lifecycle instead of relying on a long blocking MCP call or direct tool execution.

## Task contract

| Tool | Purpose |
| --- | --- |
| `agent_task_start` | Submit `prompt`, optional `cwd`/model selection, and a caller-generated `request_id`; immediately returns task and session IDs. Distinct sessions run concurrently; overflow is queued. |
| `agent_task_status` | Read state and current step/tool counts without calling a model. |
| `agent_task_wait` | Poll with a wait of at most 20 seconds; continue until `terminal: true`. |
| `agent_task_cancel` | Request native cancellation and clear queued inbox work; poll for terminal acknowledgement. Already-performed edits are not rolled back. |
| `agent_task_continue` | New request ID and prompt in a previous managed session; refuses concurrent work in that session. |
| `agent_model_request` | Read a full or hash-anchored delta request. Use `mode=full` for the first step, then `mode=delta` when available; full remains available if the base was lost. |
| `agent_model_respond` | Submit a model decision and optionally wait up to 20 seconds in the same call for the next state. |
| `bridge_info` / `bridge_self_test` | Show the actual registered tool list and registry hash; check storage, workspace and driver wiring. Self-test does not prove DSH tool execution. |

Retry `agent_task_start` with the **same request ID and identical arguments** to recover the same task; changing arguments with the same ID is rejected. Use a new ID for a genuinely new task. Avoid external UI prompts in an active managed session: the reported progress covers the owned submission-to-idle interval, not per-message attribution of externally inserted work.

Concurrency is session-scoped. One ChatGPT conversation may start several independent tasks in parallel by using distinct request IDs; each new task gets its own DSH session. A continuation intentionally reuses its previous DSH session and remains serial so that two turns cannot mutate the same agent trajectory or inbox concurrently. In external-driver mode, an agent step awaiting ChatGPT's decision yields its managed-root execution slot so another session can run. Accepted decisions reacquire a slot before DSH resumes; while waiting, the task reports `WAITING_EXECUTION_SLOT`. At most `maxConcurrentTasks + maxQueuedTasks` nonterminal managed tasks exist, including those waiting for ChatGPT. Once managed-root slots are occupied, new independent tasks enter a bounded FIFO queue and report `state: QUEUED` plus `queuePosition`. DSH owns any additional capacity limits for child subagents; the Bridge slot counter does not count each child as a separate managed root.

Model selection uses the official `sessionController.selectModel`: in this DSH version it also saves the selected model as the deployment's future default, just like the Web UI selector. Omit model arguments to leave the existing selection unchanged. The bridge does not modify provider credentials. `bridge_info.lastExecution` separately reports the last task outcome: healthy transport/storage (`ok: true`) does not mean the model account has quota or that a development task succeeded.

`harness_run`, `harness_wait(session_id)` and `harness_cancel(session_id)` remain compatibility aliases. `harness_run` returns immediately. Its optional `request_id` enables deduplication; legacy callers without it start a new task on every call. `timeout_ms` is now an inactivity lease, renewed only by a new DSH event or external model request/response, not by status polling. An independent `maxTaskLifetimeMs` caps total runtime. Refresh the ChatGPT connector's tool catalog after deployment (a new chat may be necessary for newly added tools). `bridge_info.registeredTools` and `registryVersion` describe actual MCP registration; direct `shell_exec` and filesystem tools are intentionally absent in agent-loop mode. A stale ChatGPT tool snapshot cannot be refreshed by the server itself.

The transport may disconnect while DSH continues. Task state lives at the plugin level, not the HTTP request level. Durable records are stored privately under `dshHomePath('storages/gpt-mcp-tasks')`; full prompts and tool outputs remain in DSH's session journal, not duplicated in the task index. Do not share these files publicly.

Terminal statuses: `completed`, `failed`, `blocked`, `cancelled`, `timed_out`, `lifetime_exceeded`, `interrupted`. An idle agent alone is **never** reported as completed: the owned interval must contain a durable `turn/end` with `reason.kind=completed`. This indicates that DSH completed a turn, **not independent proof that all requested tests passed**; inspect its answer and tool results. Errors and token-limit stops remain failures. On restart, unfinished records become `interrupted` and are not automatically replayed; inspect history and explicitly continue when safe.

Defaults in `cordis.patch.yml`: eight concurrent tasks, a 32-task FIFO queue with a 15-minute admission timeout, a 15-minute running-task inactivity lease, one-hour maximum lifetime, 20-second maximum polling wait and 16,000-character inline model-request threshold. Larger requests are paginated. A repeat request can transmit only changes from its predecessor within the same task, anchored by SHA-256 hashes; this is a transport optimization, not DSH history compaction. Deadline expiry cancels through DSH and waits for native quiescence; a non-cooperative native tool may delay cancellation. Task state uses atomic private-file replacement (not a multi-process database); run only one Web profile instance against this state directory. Records currently require manual retention management; do not delete records for active tasks.

`bridge_info.capabilityCoverage` reports the native DSH tool names observed in the latest external model request and which tools appeared in the most recent 50 managed task summaries. It persists only tool names and observation time, never request content or credentials. “Advertised but not used” is a coverage hint, not proof that a tool is broken or needed; UI-only DSH features do not become MCP tools merely because they appear in the Web app.

The external driver routes a live in-process subagent's model requests to its owning managed root task through DSH's durable parent-session lineage. For now, `subagent` and `subagent_fork` calls must set `run_in_background: false`; a background child can outlive the root turn, which the Bridge does not yet manage safely. The Bridge rejects that mode explicitly instead of leaving an unowned child.

`mode: legacy` is an explicit rollback/maintenance option that republishes the old direct tools. It is not used in the upgraded Web deployment.

## Install into the Web profile

From the DeepSeek Harness checkout:

```bash
pnpm dsh plugin --profile web add file:../dsh-gpt-mcp-bridge
```

Start Harness from the workspace the bridge should control:

```bash
pnpm dsh web --no-open
```

The MCP endpoint is `http://127.0.0.1:3080/mcp`; health is available at `http://127.0.0.1:3080/mcp-health`.

## Smoke test

```bash
pnpm install
pnpm smoke
pnpm test
pnpm relay-smoke
```

## ChatGPT tunnel

Point OpenAI `tunnel-client` at the MCP endpoint, then connect that tunnel from ChatGPT developer mode.

For `tunnel-client` v0.0.10, use `scripts/stdio-relay.mjs` with the
`sample_mcp_stdio_local` profile. This transport adapter avoids the known
v0.0.10 no-auth HTTP readiness bug while forwarding every tool call to the
same live Harness HTTP endpoint.

Keep the existing tunnel ID and credentials; do not create a new tunnel for this upgrade. Health and `bridge_info` show `version: 0.5.0`, `mode: agent-loop`, and `executionOwner: DSH Agent Loop`. Neither proves model execution; a real acceptance test must submit a task through the cloud tunnel and inspect DSH `tool/call`, `tool/result` and `turn/end` events plus independent output verification.

## Official references and compatibility

- [DeepSeek Harness official documentation](https://deepseek-harness.github.io/deepseek-harness/)
- [Official GitHub repository](https://github.com/deepseek-ai/deepseek-harness)
- [Architecture](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md)
- [Generated agent lifecycle](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/agent-lifecycle.md)
- [Defensive lifecycle patterns](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/defensive-patterns.md)

Implemented against the locally installed `dsh-0.1.2-alpha.4` checkout at `4e84901e64`, specifically `packages/api/session-controller` and `packages/core/agent` public contracts. Current GitHub master may expose different APIs. Upgrade DSH separately with compatibility tests; this change does not update its version or provider credentials.
