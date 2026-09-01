# Admin data browser handover

## Outcome

Added an authenticated administrator data browser at `/data-browser`. It lists every SQLAlchemy-managed application table, displays records in primary-key order with fifty-row pagination, and supports audited updates to safe scalar fields.

## Safety boundaries

- Non-administrators receive HTTP 403.
- Table names are resolved only from SQLAlchemy metadata; user-supplied table or column names are never interpolated into SQL.
- Updates use SQLAlchemy parameter binding.
- Primary keys, foreign keys, timestamps, password hashes, and audit events are not editable.
- Password hashes are not rendered.
- Database constraint failures roll back the transaction and produce a user-visible error.
- Every successful update creates a `database_record.update` audit event listing the changed field names, not their potentially sensitive values.

## Persistence and migrations

The capability edits existing mapped records and uses the existing `audit_event` table. It adds no schema, columns, or persistent data type, so no database migration is required.

## Verification

`tests/test_database_browser.py` covers administrator access, credential redaction, audited record editing, non-administrator denial, and read-only audit history. The full suite passes with 134 tests.
