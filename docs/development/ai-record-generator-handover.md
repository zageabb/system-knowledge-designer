# Focused feature handover — AI Record Generator

## Scope

Broader phase development was paused for this requested feature. Added a dedicated Ollama-backed page for schema-grounded sample record generation, adapted from Tender Designer's bounded LLM client and proposed-action flow. The left column lists tables instead of chat history.

## Outcome

- Table-first three-column workspace.
- Configurable record count, model and scenario instructions.
- Administrative Ollama URL/default-model settings with environment fallbacks and immediate activation.
- Bounded schema/existing-row prompt context.
- Strict JSON/Pydantic response contract.
- Deterministic validation of every generated row.
- Relationship-aware prompts with allowed foreign-key values from the selected dataset.
- Deterministic foreign-key validation during proposal and confirmation.
- Persisted proposed/applied/rejected `AIAction` states.
- Explicit confirm/reject UI; no direct LLM writes.
- Revalidation and active-revision drift protection on confirmation.
- Audit events for proposal, application and rejection.

## Persistent change

Added `AIAction`; migration is `migrations/versions/0004_ai_record_actions.sql`. Ollama defaults are environment-configured through `OLLAMA_URL` and `OLLAMA_MODEL`.

## Verification

`python3 -m pytest -q`: 37 passed. Tests cover schema-grounded prompting, allowed-key context, invalid generated values and references, empty parent tables, route-level relationship context, proposal-without-write, confirmation/application, and rejection-without-write.

The change was prompted by a failed sandbox containing valid rows structurally but inconsistent references: `SUPPLIER.supplier_id` contained 101–103 while generated `PURCHASE_ORDER.supplier_id` values were 2, 4, 6, 8, 10, 12, 14 and 16. The sandbox correctly rejected all eight dangling references. Generation now prevents this condition before a proposal is persisted, and sandbox build errors are displayed in the Sample Data build history.

## Known limitations

Generation is synchronous and may occupy one Flask request while Ollama responds. A persisted background job and progress UI belong to the later jobs phase. Generation still operates one table at a time, so referenced/parent rows must be created before dependent rows.

## Suggested commit

`feat: add confirmed Ollama sample record generator`
