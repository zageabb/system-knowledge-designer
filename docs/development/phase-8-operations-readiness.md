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

Background render/export execution, broader accessibility verification and release packaging remain outstanding.

## Accessibility baseline

The shared layout now includes a keyboard skip link, labelled primary navigation, a programmatically focusable main landmark and a high-visibility `:focus-visible` treatment. Non-interactive navigation placeholders were removed so they are not announced as unavailable destinations. Automated layout coverage verifies these shared guarantees; page-level semantic and contrast auditing remains outstanding.

## Production launch baseline

`wsgi:application` provides the production WSGI entry point and Gunicorn is pinned in the application requirements. Startup validation fails closed unless the session secret, administrator password, database URL and absolute managed-data path are explicitly configured. Unit tests cover accepted settings, each unsafe default and redaction of supplied secret values.
