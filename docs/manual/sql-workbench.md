# Safe SQL Workbench

The SQL Workbench runs proof-of-concept queries against the newest successful project sandbox. It does not connect to production databases.

## SQL Viewer

Open **SQL Viewer** from the project workbench for a focused query-testing page. Paste or type one statement, drag selected SQL text onto the drop area, or drop one `.sql` file. The file is read locally by the browser and placed into the editor; it is not uploaded as a managed document.

Select **Validate and test results** to run the same deterministic read-only validation used by the SQL Workbench. The query can execute only against a completed sandbox for the active model revision, with the standard authorizer, timeout and 500-row limit. Successful tests are recorded in SQL execution history.

## Validate and execute

1. Build a sandbox from the active approved model and a sample dataset.
2. Open **SQL Workbench** from the project workbench or sample-data page.
3. Enter one `SELECT` statement or read-only CTE.
4. Select **Validate** to inspect referenced tables and fields without execution.
5. Select **Validate and execute** to run the same validated statement.

Validation uses SQLGlot, not string matching. It rejects mutation, administrative commands, multiple statements, unknown tables and unknown fields. Execution adds a read-only SQLite connection, authorizer callback, managed-path check, ten-second progress timeout and 500-row result limit. Completed executions are audited and shown in recent history.

```sql
SELECT s.supplier_name, SUM(p.order_value) AS total
FROM SUPPLIER AS s
JOIN PURCHASE_ORDER AS p ON p.supplier_id = s.supplier_id
GROUP BY s.supplier_name
ORDER BY total DESC;
```

## Generate SQL from a data question

Enter a natural-language question under **Generate a grounded SQL proposal**. Ollama receives the active authoritative table/column/relationship model and must return one structured statement with explanation and assumptions. The proposal must pass the same deterministic read-only SQL parser before it is stored for review.

- **Reject** closes the proposal without changing the SQL editor.
- **Confirm and load** revalidates against the still-active model and loads the statement into the editor.
- Confirmation never executes SQL. Review the loaded statement, then separately choose **Validate** or **Validate and execute** against a successful managed sandbox.

Generated DELETE/UPDATE/INSERT/DDL, PRAGMA, ATTACH, multiple statements, unknown objects and other unsafe forms are rejected before review. If the active model changes, the proposal must be regenerated.

Diagram highlighting remains planned.
