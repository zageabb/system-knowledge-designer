# Sample data and sandbox builds

Sample data demonstrates system behavior; it is not an uncontrolled production copy. Prefer synthetic or anonymised values and assign provenance/classification when creating a dataset.

## Add representative rows

1. Approve the model revision that will define the sandbox.
2. Open **Sample data** and create a named dataset.
3. Select a table and enter one row as a JSON object.
4. Submit the row. The application checks the table, fields, types, lengths and nullability before storing a normalised row.

Example values for a supplier row:

```json
{"supplier_id": 1, "supplier_name": "Acme Components"}
```

Unknown fields, missing non-null values and incompatible types are rejected rather than silently coerced into invalid data.

## Edit or delete rows

Select **Edit** beside a stored row to open its pre-filled JSON editor. **Save changes** validates the fields and the complete dataset's relationships before persistence. The row's table cannot be changed in place.

Select **Delete row** and confirm the browser prompt to remove a row. A deletion is refused if another sample row still references it. Edit or remove dependent rows first, then delete the referenced row. Successful edits and deletions are recorded in the audit log.

## Delete a dataset

Select **Delete dataset** in the dataset header and confirm the warning to remove the complete dataset. This permanently removes its sample rows, AI record proposals, sandbox-build history and SQL execution history attached to those builds. Its managed SQLite files are removed when no other build record references the same file. The project and its model revisions are unaffected.

## Build the sandbox

Select **Build sandbox** on a dataset. The materialiser uses only the active approved revision, creates a new SQLite database beneath the application-managed project directory, creates typed tables/keys/relationships, loads validated rows and runs a complete foreign-key integrity check. A failed build is recorded but is not selected by the SQL Workbench.

The build record retains model revision, dataset, row count and a reproducible hash. The LLM and browser never choose the SQLite path.
