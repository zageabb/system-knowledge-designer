# Development roadmap

| Phase | Next acceptance evidence |
|---|---|
| 1 completion | Embedded SVG preview; composite/include grammar; 10/50/100 table render benchmarks; PNG dimension tests |
| 2 | Full catalogue CRUD/sync, Alembic upgrade path, structured revision diff, includes, repository/admin pages (source diff/restore and stale-save protection delivered) |
| 3 | CSV import/idempotency, dataset versions, saved examples, diagram highlighting and cross-project integrity (typed rows, deterministic builds and safe SQL workflow delivered) |
| 4 | Optional MSG/OCR, aliases and richer filters (multi-format ingestion, versions, deletion, locators, FTS5, citations, federation, bounded graph, links, coverage and persisted evidence snapshots delivered) |
| 5 | Additional confirmed mutation actions and multi-exchange context (Ollama, bounded cited history, SQL proposals, typed/manual/opt-in model-selected read tools, activity views, SQL diagram highlighting, confirmed document-link proposals and explicit single-parent follow-ups delivered) |
| 6 complete | Background execution and cooperative running-request cancellation delivered alongside sanitised review-before-send Wikipedia research, persisted progress/citations, local-only failure mode, selected evidence promotion, unsent cancellation and reviewed retries |
| 7 complete | Central project links, bounded traversal, trusted aliases, explicit selected-document attachments, alias-aware federation and persisted integrity scans delivered |
| 8 | Background render/export, scale profiles, accessibility, deployment/operations readiness |

No row in this roadmap is considered delivered until its automated acceptance tests pass.

## Documentation workstream

The user manual and normative ER language syntax reference are continuous workstreams across all phases. Phase 1 establishes the document structure and documents the executable grammar/editor. Each later phase adds its workflows and syntax before that phase can close. Phase 8 produces versioned release outputs, completes clean-install walkthrough verification, validates every documented `.erd` example against the parser, checks links and commands, and publishes optional HTML/PDF editions from the Markdown sources.

Detailed requirements and acceptance checks are in [`documentation-plan.md`](documentation-plan.md).
