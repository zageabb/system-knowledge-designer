# Phase 3 slice — sample data, sandbox and safe SQL

## Outcome

Implemented classified sample datasets, typed JSON row entry, editing and guarded deletion, deterministic per-project SQLite materialisation, build hashes/history, SQLGlot read-only validation, SQLite defence-in-depth execution, result grids and execution history.

## Architecture

- `services/sample_data.py` validates and normalises values against the independent ER intermediate model.
- Row edits and deletions validate all remaining dataset relationships before persistence, preventing dangling foreign keys.
- Whole-dataset deletion explicitly removes dependent AI actions, SQL executions and sandbox-build records, then safely cleans unreferenced files beneath the managed data root.
- `services/sandbox.py` translates the active approved revision to SQLite, loads deterministic rows, scans foreign-key integrity and atomically publishes a content-addressed sandbox.
- `services/sql_safety.py` separates parser validation from execution. The executor receives only validated SQL and a catalogue-stored managed path.
- Browser routes orchestrate these services; they do not implement type or SQL safety rules.

## Persistent models and migration

Added `SampleDataset`, `SampleRowDefinition`, `SandboxBuild` and `SQLExecution`. Migration SQL is recorded in `migrations/versions/0003_sample_sandbox_sql.sql`.

## Dependencies

SQLGlot 27.20.0 provides maintained SQL AST parsing. SQLite remains Python standard-library functionality.

## Verification

`python3 -m pytest -q`: 40 passed across the application. Phase coverage includes validated row editing, guarded deletion, relationship integrity, deterministic build, real join/aggregation execution, the full browser workflow, managed-path enforcement and rejection of DELETE, PRAGMA, ATTACH, unknown objects and multiple statements.

## Security and limitations

Execution uses SQLite read-only URI mode, authorizer denials, a progress timeout and row limit. The validator currently checks columns against the project-wide known-column set; a later refinement will resolve aliases/table scopes more precisely. CSV import, dataset versioning, saved SQL examples, diagram highlighting, cross-project attachment and natural-language proposals remain Phase 3/5/7 work.

## Suggested commit

`feat: add deterministic sample sandboxes and safe SQL workbench`
