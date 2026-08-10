# Phase 8 slice — operations readiness probes

## Outcome

Separated process liveness from dependency readiness. `/health` remains a minimal unauthenticated liveness response. `/ready` checks the catalogue database, writable managed storage and the Graphviz executable required by diagram rendering.

## Boundaries

- Readiness checks are deterministic and do not call Ollama or external networks.
- Failure responses use HTTP 503 and generic details; database exceptions and managed paths are not returned.
- The probe performs no persistent writes and does not alter application state.

## Verification

`tests/test_readiness.py` covers the healthy response, missing storage/Graphviz, database failure and exception-detail redaction.

## Remaining Phase 8 scope

Background render/export execution, broader accessibility verification and production deployment packaging remain outstanding.
