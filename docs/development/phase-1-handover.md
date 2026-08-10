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

`python3 -m pytest -q`: 8 passed, including real Graphviz SVG and 1×/4× PNG output with dimension assertions. Launch: `.venv/bin/flask --app app run --host=127.0.0.1 --port=5015`; URL: <http://127.0.0.1:5015>.

## Known limitations

Graphviz must exist on the host for the embedded preview and exports. Composite keys/relationships, includes, schema namespaces, Mermaid import, large-model benchmarks and revision diff/restore remain Phase 1/2 work. This is a verified vertical slice, not the full first usable release.

## Suggested commit

`feat: establish authenticated ER modelling vertical slice`
