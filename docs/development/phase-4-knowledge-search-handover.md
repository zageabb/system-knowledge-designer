# Phase 4 slice — managed text knowledge and local search

## Outcome

Delivered Phase 4 vertical slices for multi-format ingestion, managed provenance, immutable versions, precise locators, FTS5/citations, audited deletion, federated retrieval, bounded graph traversal, revision-bound document/passage links, coverage diagnostics and persisted evidence snapshots.

## Architecture and security

- `services/knowledge.py` owns validation, extraction, chunking and FTS operations independently of Flask routes.
- Original files are stored only below the configured project data root with generated names; supplied paths are never used.
- Search parameters are bound, result counts and query terms are bounded, and all rendered document text remains auto-escaped.
- Evidence stays local and project-scoped. It is not treated as an instruction or sent to an LLM/external provider.
- Schema search reads revision-scoped catalogue records; relationship evidence reads the active typed model; sample search is bounded and displays dataset classification.
- Document deletion removes its FTS rows and catalogue children transactionally, then removes only an original file resolved beneath the managed data root.
- PDF pages/text and spreadsheet cells are bounded. Office packages are screened for invalid ZIP structure, entry count, expanded size and extreme compression ratio before document libraries parse them.
- Standalone ZIP processing never writes members to disk, is non-recursive, accepts only UTF-8 TXT/Markdown/CSV members and applies bounded entry, expansion and compression-ratio checks. EML extraction reads plain-text bodies as inert evidence.
- `KnowledgeLink` stores project, document, defining revision, typed target key and actor. Browser creation validates targets against the active parsed model; no AI process applies links.
- Multi-concept schema queries use bounded breadth-first traversal of the active typed relationship graph, returning shortest field-level paths up to four hops without LLM inference.
- `DocumentVersion` assigns a family UUID, monotonic version number and predecessor. New uploads pass the full ingestion pipeline and retain old chunks/citations; deleting one version reconnects remaining lineage.
- Coverage compares unique linked table/column targets with the active model, counts unlinked documents, and reports historical links whose targets disappeared without mutating them.
- `ChunkKnowledgeLink` applies the same active-model validation, revision binding and auditing to one precise cited passage. Passage evidence contributes to coverage independently of whole-document links.
- `EvidenceRecord` captures the search query/filter, active model revision, actor and bounded deterministic result families. Snapshots can be reopened or explicitly deleted and do not execute actions.

## Persistence

Added `KnowledgeDocument` and `DocumentChunk`, plus the external-content FTS5 index. Migration evidence is `migrations/versions/0005_knowledge_documents.sql`.

## Verification

`python3 -m pytest -q`: 62 passed. Focused coverage includes extraction, cleanup, isolation, federation, traversal, immutable versions, links, coverage, stale detection, and evidence snapshot save/open/delete.

## Remaining Phase 4 scope

Optional MSG and OCR, aliases and richer filters remain outstanding. EML HTML bodies and attachments are not yet indexed. Grounded natural-language answers over evidence belong to Phase 5. This slice does not claim Phase 4 completion.
