# Phase 7 slice — central project graph

## Outcome

Added a central, typed project-link catalogue, bounded cross-project traversal, trusted discovery aliases, explicit selected-document attachments, alias-aware federation and persisted portfolio integrity scans.

## Boundaries

- `services/project_graph.py` owns deterministic alias normalization, link validation, breadth-first traversal and integrity checks independently of Flask.
- Links use a fixed relationship vocabulary, reject self-links and are unique per source, target and relationship type.
- Traversal treats links as navigable in either direction and is bounded to three hops and fifty projects.
- Normalized aliases are globally unique. Only administrators can mark an alias trusted.
- Integrity scans persist immutable JSON evidence and currently check missing endpoints, self-links, invalid active revisions and orphan aliases.
- Project links do not automatically expose documents or samples across project boundaries. A second explicit attachment action selects one source document for one consumer project, and search results retain source-project attribution.
- Trusted aliases resolve schema only for directly linked projects and only when the alias appears in the query. Untrusted aliases never expand search.
- Integrity scans also detect attachments whose document ownership is inconsistent or whose project link has disappeared.

## Persistence

Migration `migrations/versions/0017_project_graph.sql` adds `ProjectLink`, `ProjectAlias` and `ProjectIntegrityScan`. Migration `migrations/versions/0018_cross_project_attachments.sql` adds `CrossProjectAttachment`.

## Verification

`python3 -m pytest -q`: 88 passed. Focused tests cover normalization, validation, bounded traversal, browser persistence, trusted aliases, clean scans, self-link rejection, normalized duplicate rejection, attachment isolation, explicit-link enforcement, source attribution and trusted-alias schema federation.

## Phase status

The acceptance suite covers central links, bounded traversal, trusted aliases, selected attachments, integrity scans and alias-aware federation. Phase 7 is complete.
