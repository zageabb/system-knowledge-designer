# Phase 0 — repository audit and architecture

## Audit basis

Audited the local checkouts at their remote `main` heads on 2026-07-31 without modifying either repository:

- `zageabb/tender_designer` — `43d66f7` (`Keep general search input visible`)
- `zageabb/mermaid_final` — `6ea6729` (`Add complete Mermaid manuals`)

Tender Designer has a sound Flask factory with Flask-Login and CSRF, blueprints, SQLAlchemy/Alembic, managed upload paths, extraction services, Ollama task boundaries, persisted job/lease patterns, page-aware chat and proposed actions, settings/prompts, audit-like LLM logs, and an agentic search service with deterministic fallback. Its principal debt is a large single `models.py`, domain coupling in routes/services, and some schema compatibility work outside normal migrations.

Mermaid Final is a monolithic Flask application with a polished three-pane editor, debounced live rendering, draggable panes, contextual help, zoom/pan, project folders, active/inactive revisions, `%% INCLUDE`, and export. The repository model is file/JSON authoritative and its client renderer uses CDN dependencies and `securityLevel: loose`; those are unsuitable foundations for untrusted system models.

## Reuse / refactor / replace

| Area | Decision | Treatment |
|---|---|---|
| Flask factory, login, CSRF | Reuse pattern | Small factory, extension initialisation, protected routes |
| Managed paths, worker leases | Refactor later | Project-scoped path service and generic persisted jobs |
| Ollama, prompt and page context | Refactor later | Provider interface and bounded evidence contract |
| General Search | Refactor later | Domain-neutral provider with privacy-sanitised outbound plans |
| Upload/extraction | Refactor later | Typed extractors, locators, limits and FTS indexing |
| Three-pane workbench | Reuse UX | Server-authoritative Graphviz preview and local static assets |
| Repository revisions/includes | Refactor | Database revisions; managed includes with cycle detection |
| Mermaid client rendering | Replace | Lark IR → safe DOT argv → Graphviz SVG/PNG |
| JSON/file authority | Replace | SQLAlchemy catalogue and immutable revision snapshots |
| Monolithic modules | Replace | Route/service/model packages as capabilities grow |

## Final directory plan

`app.py`, `config.py`, `database.py`; domain models; capability routes; independent `services/er_language`, renderer, catalogue, revision, document, search, sandbox, SQL, Ollama, tools, jobs and audit services; templates/static; Alembic migrations; project-managed data; unit/integration/workflow/scale tests; phase handovers under `docs/development`.

The first vertical slice deliberately keeps models/routes compact. Split thresholds are documented in the roadmap rather than creating empty packages.

## Database relationships

`SystemProject` owns immutable `DiagramRevision` records and points to one active approved revision. Each revision owns its materialised `TableDefinition` and `RelationshipDefinition`; tables own ordered `ColumnDefinition` rows. Future project links connect projects centrally. Documents/chunks, datasets/rows/builds, SQL examples/executions, searches/evidence, chats/actions, jobs and audit events reference a project and, where evidence integrity requires it, a precise revision.

Sandboxes remain separate managed SQLite files and store the originating model/dataset hashes in catalogue-side `SandboxBuild` records.

## ER grammar proposal

Core: `erModel`, `dialect`, `direction`, `subjectArea`, `table|view`, typed fields, `PK|FK|not_null|unique`, key/value type parameters, and field-to-field `relationship` blocks. The parser creates Pydantic IR independent of Flask/rendering. Grammar versions will add descriptions, schemas, composite keys, indexes, cross-project aliases, includes and layout hints without regex parsing.

## Rendering proof plan

Generate escaped DOT with HTML table labels and stable field `PORT`s; run `dot` through a fixed argument array; test edge endpoints in DOT, SVG validity, unique node IDs, PNG signatures/dimensions and 1×/2×/4×/8× output. Benchmark generated 10/50/100-table fixtures, then move large renders to persisted jobs.

## Search and AI-tool architecture

Deterministic retrievers produce one `Evidence` contract across catalogue exact/alias matching, schema graph traversal, FTS5 documents, bounded sample values and external URLs. The composer receives selected evidence only. A Pydantic tool registry declares read/write, permission, confirmation, timeout, idempotency and audit policy. Writes create `AIAction` proposals; only confirmed actions call deterministic services. External search consumes sanitised generic terms, never raw internal evidence.

Codex may also integrate through the versioned, bearer-authenticated control API described in [`docs/overall-design.md`](../overall-design.md). The API is disabled by default, controlled from administrative settings, and delegates to deterministic application services. It permits inspection, validation, project creation and draft proposals, but not revision approval or unrestricted execution.

## Phased sequence

0 audit/plan → 1 ER proof → 2 catalogue/repository → 3 sample/sandbox/SQL → 4 knowledge/local search → 5 grounded assistant/tools → 6 external search → 7 cross-project systems → 8 scale/hardening. Acceptance evidence, migrations, test output and limitations are recorded per phase.

## Assumptions and blocking decisions

Accepted brief assumptions: local single user first; browser UI; SQLite catalogue and per-project sandboxes; Graphviz; FTS5; Ollama; synthetic/anonymised samples. No genuinely blocking product decision was found. Server exposure requires a non-default secret/password and HTTPS reverse proxy.
