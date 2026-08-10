# Assistant SQL answering development item

**Status:** Delivered with automated acceptance coverage.

## User outcome

The grounded Assistant must answer quantitative questions such as “How many purchase orders are there?”, “What is the total open order value?” and “Which suppliers have unpaid invoices?” using the selected project's managed sample sandbox.

## Required pipeline

1. Detect that the question requires structured data rather than document or schema retrieval alone.
2. Build a SQL proposal using the active approved model as the only schema context.
3. Pass the proposal through the existing deterministic read-only SQL validator.
4. Execute only the validated statement against the project's current successful managed sandbox using the existing bounded executor.
5. Convert the bounded result into Assistant evidence containing the exact statement, referenced objects, column names, rows, row count, sandbox build ID and model revision ID.
6. Generate the natural-language answer from that evidence and require a citation to the persisted tool call or SQL execution record.

The AI proposes SQL but never invokes SQLite or selects a database path directly. Validation, project ownership, sandbox selection, timeouts and row limits remain deterministic application responsibilities.

## Tool boundaries

- Add an opt-in `sql.query` Assistant read tool for generated, validated `SELECT` and `WITH ... SELECT` statements.
- Add a deterministic `samples.aggregate` tool for common count, sum, minimum, maximum and average questions where a typed operation is safer than free-form SQL.
- Both tools require an active approved model and a completed sandbox built from that same revision.
- Reuse the SQL safety allow-list: no mutation, pragma, attach, multiple statements, unknown tables or unknown fields.
- Execution uses only the stored managed sandbox path after the existing allowed-root check; tool arguments never contain a path.
- Persist and audit proposals, validation failures, executions and evidence supplied to the final answer.
- Keep model-selected execution off by default per question. The UI must clearly state that enabling it may run validated read-only queries against synthetic/local sandbox data.

## Acceptance evidence

- “How many purchase orders are there?” returns the exact deterministic count from `PURCHASE_ORDER` and cites the SQL tool result.
- Aggregation, grouping, filtering and join questions return results matching direct bounded executor output.
- A generated `DELETE`, `PRAGMA`, `ATTACH`, multi-statement query, unknown object or path-bearing request is rejected and never executed.
- A missing, failed, stale or cross-project sandbox produces a clear limitation instead of an inferred answer.
- Changing the active revision invalidates an older sandbox for Assistant execution.
- Result evidence is bounded and persisted; the final answer cannot cite an unknown tool result.
- Manual and model-selected calls are project-scoped and appear in Assistant tool activity and the audit log.
- Tests cover proposal generation, validation, execution, citation enforcement, opt-in behavior and all rejection paths.

## Delivery evidence

The Assistant screen provides a per-question **Allow Ollama to build and run one validated read-only sandbox query** control. `sql.query` and `samples.aggregate` share the existing validator and bounded executor. Successful queries create both an audited `AssistantToolCall` and `SQLExecution`; the exact bounded result is supplied as `tool:{id}` evidence to the grounded answer.
