# Catalogue, revisions and exports

## Structured catalogue

Select **Catalogue** in the workbench. The page shows the active approved revision when available, otherwise the newest draft. A `revision_id` selection from revision history shows that exact historical snapshot.

Tables are grouped by subject area and list ordered fields, authored types, key markers and nullability. Relationships list their exact field endpoints, cardinality and label.

## Revision history

Revision history records the status, model hash, note and creation time for every draft, approved and inactive snapshot.

- **Compare prior** shows a unified `.erd` source diff against the preceding revision.
- **Restore as new** parses and validates historical source, then creates a new draft. It never mutates or deletes history.
- Approval makes the selected revision active and marks the previous approved revision inactive.

Model hashes allow operators and later sandbox services to detect drift between structured revisions and derived artefacts.

