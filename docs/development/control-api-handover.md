# Codex control API handover

## Outcome

Added a versioned `/api/codex/v1` integration for direct structured inspection and bounded control. It is disabled by default, requires an environment bearer token, can be turned on or off immediately by an administrator, audits writes, and never exposes approval, shell, arbitrary filesystem or SQL execution.

## Persistent changes and migration

`AppSetting` stores the non-secret enabled state. `migrations/versions/0002_control_settings.sql` defines the new table. The bearer token remains in `CODEX_CONTROL_TOKEN` and is never persisted or displayed.

## API surface

Read: status, project list and project/revision metadata. Deterministic operation: validate ER source. Writes: create project and create validated draft revision. Material approval remains browser-only.

## Verification

Automated coverage demonstrates disabled-by-default behavior, bearer authentication, immediate UI enable/disable, structured validation, inspection, audited project/draft creation, rejection of invalid source, and absence of an API approval route.

## Configuration

Set a long random `CODEX_CONTROL_TOKEN`, restart the process, sign in as an administrator, open **Control Settings**, and enable the API. Disable the checkbox to revoke API access immediately.

## Known limitations

The initial API intentionally does not expose documents, search, sandbox builds, SQL execution, job control or AI actions because those deterministic domain services are not implemented yet. Add them only with typed contracts, permissions, audit and confirmation policy.
