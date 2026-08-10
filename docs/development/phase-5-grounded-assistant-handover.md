# Phase 5 slice — grounded local assistant

## Outcome

Added a project-scoped Ollama assistant with bounded cited evidence/history, schema-grounded confirm-to-load SQL proposals, explicit typed read tools, opt-in model-selected read-tool planning with persisted activity, validated-query diagram highlighting, confirmed document and precise chunk-link proposals, and explicit multi-exchange follow-up context.

## Boundaries

- `services/grounded_assistant.py` owns the structured response contract, bounded prompt and citation allow-list validation.
- Retrieved content is explicitly treated as untrusted evidence rather than prompt instructions.
- The assistant cannot execute SQL or directly apply model-selected actions. Read tools and mutation proposals are separately opt-in.
- Ollama URL/model use the same administrative settings as the AI Record Generator.
- `services/ai_sql.py` supplies only the active typed schema/relationships and sends generated SQL through `services/sql_safety.py`. `AIAction` records proposed/rejected/applied review state; applying means loading into the editor, not execution.
- `services/assistant_tools.py` is an allow-listed dispatcher for `schema.inspect`, `documents.read_chunk` and `sql.validate`. Inputs are typed/scoped, validation never executes, unknown tools are rejected, and `AssistantToolCall` records every outcome.
- The optional planner returns at most three structured requests. The application validates names, executes only the read dispatcher, records the actor as `ollama:{user}`, and adds successful results to the final evidence allow-list.
- The SQL Workbench derives table and field highlights only from deterministic validation output. Confirmed AI proposals open this impact diagram but remain unexecuted until the user separately chooses execution.
- `services/assistant_actions.py` exposes only `knowledge.link_document` and `knowledge.link_chunk`. Ollama output is constrained to existing document or chunk IDs and exact active-model targets, then persisted as a proposed `AIAction`. A separate user confirmation revalidates project/revision/target/uniqueness before the normal `KnowledgeLink` or `ChunkKnowledgeLink` write.
- Follow-up context is user-selected and limited to three prior exchanges in the same project. Each bounded prior answer/citation set becomes untrusted evidence; `AssistantContextLink` persists every selected lineage edge without implicitly replaying history.

## Persistence

Added `AssistantExchange` and `AssistantContextLink`; migration evidence is `migrations/versions/0010_assistant_exchanges.sql`, `migrations/versions/0012_assistant_context_links.sql` and the multi-parent constraint migration `migrations/versions/0020_multi_exchange_context.sql`.

## Verification

`python3 -m pytest -q`: 102 passed. Tests cover grounded citations/history, SQL proposals, manually invoked tools, bounded allow-listed planning, rejection of model-requested shell access and unlisted mutations, automatic read-tool audit identity, tool-result grounding, query diagram highlighting, confirm-before-write document and chunk links, selected multi-exchange lineage and cross-project isolation.

## Phase 5 status

Phase 5 is complete. Assistant SQL answering, deterministic sample aggregation, bounded explicit multi-exchange context, and confirmed whole-document and precise chunk-link actions are delivered. The SQL flow reuses AI SQL proposal building, deterministic read-only validation and bounded managed-sandbox execution, then supplies the persisted result as cited answer evidence. See [`assistant-sql-answering-plan.md`](assistant-sql-answering-plan.md).
