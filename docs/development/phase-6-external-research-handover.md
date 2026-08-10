# Phase 6 slice — privacy-controlled external research

## Outcome

Added a disabled-by-default, review-before-send Wikipedia research workflow with deterministic privacy sanitisation, bounded background execution, persisted progress/results, bounded citations, an explicit local-only failure path, selected citation promotion into local knowledge, and audited cancel/retry lineage.

## Boundaries

- `services/external_research.py` removes common sensitive shapes and limits outbound text to twelve generic terms. It calls one fixed HTTPS Wikipedia API endpoint; users cannot supply a provider URL.
- Preparing a job is local. The exact outbound query is displayed and requires a separate confirmation before network access.
- `ExternalResearchJob` persists original/local text, outbound text, provider, proposed/running/completed/failed status, timestamps, errors and at most five citations.
- External access is controlled by `external_research_enabled` under administrative Settings and is off by default. Disabled mode never invokes the provider.
- Provider failures leave local data unchanged and direct the user to project-local knowledge search. Results remain external evidence and are not silently indexed or supplied to Ollama.
- Promotion is a separate user action on one citation. `services/knowledge.py` validates the fixed Wikipedia page URL, writes a managed Markdown source, creates a public/external document and FTS chunk, and preserves the source URL. `ExternalResearchPromotion` prevents duplicate job/citation imports.
- Proposed and running jobs can be cancelled. Only failed jobs can be retried; retry creates a new proposed job and never sends automatically. `ExternalResearchJobEvent` records cancellation and source-to-retry lineage.
- Confirmed requests run on a two-worker application executor, keeping provider latency outside the HTTP request. A running job can be cooperatively cancelled; its state changes immediately and any late provider response is discarded without persisting citations.

## Persistence

Added `ExternalResearchJob`, `ExternalResearchPromotion` and `ExternalResearchJobEvent`; migration evidence is `migrations/versions/0013_external_research_jobs.sql`, `migrations/versions/0014_external_research_promotions.sql`, `migrations/versions/0015_external_research_job_events.sql` and lifecycle timestamp migration `migrations/versions/0016_external_research_lifecycle.sql`.

## Verification

`python3 -m pytest -q`: 83 passed. Tests cover sensitive-shape removal, term bounds, insufficient generic queries, review-before-send state, zero provider calls while disabled, persisted citations, local-only provider failure, explicit promotion, provenance, versioning, FTS visibility, duplicate prevention, background dispatch, cooperative running cancellation, late-result suppression and review-required retry lineage.

## Phase status

The acceptance suite now covers the remaining background execution and running-request cancellation scope. Phase 6 is complete.
