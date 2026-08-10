# Security model

Login and CSRF protect state changes. Secrets belong in environment variables. ER text is parsed, escaped into DOT and passed to Graphviz over stdin with a fixed argument array. Managed output paths derive only from database integer IDs/revision numbers. AI has no shell/filesystem/session access and AI-suggested writes require explicit confirmation. SQL execution must pass SQLGlot validation, SQLite authorizer enforcement, timeout and row limits against managed sandboxes only. External queries must be privacy-sanitised and audited.

Assistant mutation planning is separately opt-in and restricted to the typed `knowledge.link_document` proposal. Model output cannot apply the link. Confirmation revalidates document ownership, active revision, target membership and uniqueness, then calls the deterministic domain operation and records the result.

External research is disabled by default and uses one fixed HTTPS Wikipedia API endpoint. A deterministic local pass removes common sensitive shapes and bounds the query to twelve generic terms. The user reviews the exact outbound text and confirms a persisted proposed job before any request occurs. Provider URLs are not user-configurable, responses are bounded, and failures do not alter local project data.

External citations enter local knowledge only through an explicit per-result promotion. Promotion revalidates the fixed Wikipedia URL shape, stores a bounded excerpt in an application-managed file, labels provenance/classification, indexes it through the normal FTS boundary and prevents duplicate promotion of the same job result.

Cancelling a proposed external job occurs before any provider call. Retrying a failure creates a new proposed job linked by an immutable event; it does not resend until the user separately confirms. Status gates prevent replay of completed or already-active jobs.

The default credentials and development secret are unsafe for network access. Bind to `127.0.0.1` unless secure credentials and an HTTPS reverse proxy are configured.

## Codex control API

Codex control is disabled by default and can be switched off immediately from Control Settings. When enabled it requires an environment-only `CODEX_CONTROL_TOKEN`, compared using a timing-safe operation. The API exposes versioned, typed operations rather than shell, filesystem, ORM-session or arbitrary SQL access. Writes pass deterministic validation and create audit events atomically. Draft revisions cannot be approved through the control API.

## Sandbox SQL

Sample databases are generated beneath application-managed project directories from an active approved revision. SQL is parsed with SQLGlot and restricted to one read-only query over known catalogue objects. SQLite connections use read-only URI mode, an authorizer that denies mutation/DDL/ATTACH/DETACH/PRAGMA and filesystem-related functions, a progress timeout, a 500-row limit and a check that the resolved sandbox path remains beneath the configured data directory.

## AI-generated sample rows

The record generator sends one selected table schema, user instructions and at most 20 existing example rows to the configured local Ollama endpoint. Prompts prohibit real personal/confidential data, but generated content remains untrusted. Pydantic validates response structure and deterministic sample validators check every field. Rows remain a persisted proposal until explicit confirmation, are revalidated on application, and are rejected if the active model/dataset context changed.
