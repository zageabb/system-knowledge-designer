# Phase 1 handover — executable ER vertical slice

## Outcome

Implemented the minimal grammar, typed IR, semantic relationship validation, stable boundary-anchored field ports, a server-rendered SVG preview with zoom controls, safe Graphviz subprocess boundary, authenticated project workbench, structured draft revisions, approval/inactive history and export endpoints.

The workbench uses page-level horizontal overflow for narrow viewports and independent vertical pane scrolling, keeping source, preview, assistant, toolbar and save/export controls reachable on smaller screens.

## Architectural decisions

- Lark LALR grammar rather than regex parsing.
- Pydantic IR independent of Flask and rendering.
- Graphviz invoked with an argument array and stdin; no shell.
- Revision source plus canonical model JSON/hash is immutable.
- Materialised catalogue rows are revision-scoped, preventing draft/approved drift.

## Dependencies

Lark (grammar), Pydantic (IR/contracts), Flask extensions (persistence/auth/CSRF), Graphviz system executable (rendering). SQLGlot is pinned now for Phase 3 but is not claimed as implemented functionality.

## Migrations

Baseline SQL migration is in `migrations/versions/0001_initial.sql`. Runtime `create_all` currently bootstraps empty local/test databases; Phase 2 must replace this convenience with Alembic-managed upgrades before it is declared complete.

## Test/launch evidence

The current suite contains 97 tests, including real Graphviz SVG and 1×/4× PNG output with dimension assertions, ordered composite relationship validation, managed-include isolation/cycle/immutability checks, and generated 10/50/100-table SVG profiles. On the recorded development host those scale cases completed in 0.17s, 0.19s and 0.21s respectively. Launch: `.venv/bin/flask --app app run --host=127.0.0.1 --port=5015`; URL: <http://127.0.0.1:5015>.

## Known limitations

Graphviz must exist on the host for the embedded preview and exports. Schema namespaces and Mermaid import remain later language work. Managed project-scoped includes with cycle detection, immutable resolution snapshots, composite key participation, ordered composite relationships, large-model profiles and revision diff/restore are delivered.

## Phase status

The Phase 1 acceptance suite covers the embedded preview, composite relationships, managed includes, scale profiles and PNG dimensions. Phase 1 is complete.

## Suggested commit

`feat: establish authenticated ER modelling vertical slice`
