# Phase 2 slice — catalogue and revision repository

## Outcome

Implemented a structured catalogue view for any project revision, conflict-safe editor saves, `.erd` and structured JSON exports, unified source comparison, and restore-as-new. Historical revisions remain immutable, and restoring reparses source into a new structured draft.

Catalogue relationship rows use a consistent one-to-many reading order: the referenced parent field is shown under **One**, followed by the foreign-key dependant under **Many**. This is a presentation rule only; authoritative source and stored foreign-key direction remain unchanged.

The latest catalogue revision is editable. Users can add and rename tables, add and edit fields and their markers, and add or edit one-to-many relationships. Every catalogue save validates the complete structured model, creates an immutable draft revision, and deterministically regenerates canonical ER source; saving ER source in the workbench continues to rematerialise the catalogue in the opposite direction. Historical catalogues remain read-only.

Field data types use a controlled dropdown containing common ER types while retaining any existing custom type. Relationship table references are selected from the revision catalogue, and each relationship field dropdown is dynamically limited to fields belonging to its selected table; the server still validates every submitted reference.

Tabulator 6.5.0 is vendored under its MIT licence and progressively enhances every server-rendered data table across the application. Grids gain sortable and movable columns, text filters for high-cardinality columns, dropdown filters for bounded value sets, responsive collapse and local pagination above twenty rows. Existing form controls, links and no-JavaScript HTML tables remain the behavioural source, while the external-research activity grid exposes a safe live-update bridge for polling.

The documentation workstream now has a real user manual and normative ER syntax reference. Every fenced `.erd` example is executed through the current parser during tests, and local Markdown links are checked.

## Files and architecture

- `services/revisions.py` owns revision creation and source diff behavior.
- Catalogue routes read revision-scoped structured rows; they do not reparse source for display.
- Editor saves carry the revision number that was loaded and return HTTP 409 when a newer revision exists.
- Restore delegates to the parser and revision service, then writes an audit event in the same transaction.
- Manual source is under `docs/manual/`; normative language documentation is under `docs/er-language/`.

## Database migrations

No new persistent model was required for this slice. It uses the existing revision-scoped catalogue schema. The repository still requires replacement of development `create_all` bootstrapping with an Alembic-managed baseline before Phase 2 can be declared complete.

## Tests

`python3 -m pytest -q`: 18 passed. New coverage proves catalogue revision selection, source/model exports, unified comparison, restore-as-new, stale-save rejection, parser-valid documentation examples and local documentation links.

## Demonstration

Create two revisions with a field change. Open Revision history, compare the newest revision to its predecessor, inspect either structured catalogue snapshot, export source/JSON, restore the older revision as a new draft, and verify the history now contains three immutable revisions.

## Known limitations and next work

Revision comparison is source-level; a structured object diff should follow. Includes, composite keys, catalogue CRUD/forms, concurrency tokens beyond revision number, and Alembic adoption remain Phase 2 work. The manual documents only delivered workflows and must grow with each phase.

## Suggested commit

`feat: add structured catalogue and revision repository workflows`
