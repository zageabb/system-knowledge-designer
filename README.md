# System Knowledge Designer

Local-first executable system knowledge platform. The current verified slices provide authenticated structured modelling and revisions, deterministic sample sandboxes and safe SQL, confirmed AI sample proposals, and managed TXT/Markdown knowledge with local FTS5 search and citations.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/flask --app app run --host=127.0.0.1 --port=5015
```

Set the environment values from `.env` in your shell (Flask does not load it without `python-dotenv`). Open `http://<server-ip>:5015` and use the configured admin credentials. The development defaults are `admin` / `change-me`; change them before any network-accessible run.

Graphviz's `dot` executable is required for SVG/PNG export. On macOS: `brew install graphviz`.

For a production WSGI launch, explicitly configure secure `SECRET_KEY` and `ADMIN_PASSWORD` values, `DATABASE_URL`, and an absolute `DATA_DIR`, then run:

```bash
.venv/bin/gunicorn --bind 0.0.0.0:5015 --workers 2 --timeout 120 wsgi:application
```

The production entry point rejects missing or development-default security settings. Use `/health` for liveness and `/ready` for dependency readiness.

To add the idempotent synthetic procurement demonstration to the local database:

```bash
python3 -m scripts.seed_demo
```

## Demonstration

1. Sign in and create a project.
2. Validate the starter Supplier/Purchase Order model.
3. Create a draft revision, inspect the structured counts, and approve it.
4. Open Revision history and verify its model hash/status.
5. Export SVG or a 4× PNG.

## Architecture and delivery evidence

- [Phase 0 audit and architecture](docs/development/phase-0-audit-and-architecture.md)
- [Phase 1 handover](docs/development/phase-1-handover.md)
- [Development roadmap](docs/development/roadmap.md)
- [Overall design and Codex control API](docs/overall-design.md)
- [Manual and ER syntax documentation plan](docs/development/documentation-plan.md)
- [User manual](docs/manual/index.md)
- [ER language syntax reference](docs/er-language/index.md)
- [Security model](docs/security.md)
- [Backup and restore](docs/backup-and-restore.md)

## Important current boundary

This repository does **not** yet claim final release readiness. Background render/export, CSV and dataset-version workflows, optional MSG/OCR ingestion, page-level accessibility verification and release packaging remain roadmap work and are not represented by placeholder success paths.
