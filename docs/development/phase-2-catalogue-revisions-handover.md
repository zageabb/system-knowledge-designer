# Phase 2 slice — catalogue and revision repository

## Outcome

Implemented a structured catalogue view for any project revision, conflict-safe editor saves, `.erd` and structured JSON exports, unified source comparison, and restore-as-new. Historical revisions remain immutable, and restoring reparses source into a new structured draft.

Catalogue relationship rows use a consistent one-to-many reading order: the referenced parent field is shown under **One**, followed by the foreign-key dependant under **Many**. This is a presentation rule only; authoritative source and stored foreign-key direction remain unchanged.

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
