# Administrator data browser

Open **Data browser** from the primary navigation while signed in as an administrator. Select a mapped application table to see up to fifty records at a time, ordered by primary key. Use **Previous** and **Next** to move between pages.

Editable values are shown as form fields. Select **Save** on one row to update that record. Database constraints still apply, and a failed update is rolled back. Successful edits are recorded in the audit log with the table, record ID, and changed field names.

The browser deliberately protects primary keys, foreign keys, timestamps, password hashes, and audit events. Password hashes are never displayed. Use the feature for deliberate administrative corrections; use the normal project, revision, sample-data, and settings workflows for routine work because those pages provide richer domain validation.
