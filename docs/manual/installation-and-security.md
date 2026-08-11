# Installation and secure local launch

## Requirements

- Python 3.11 or later.
- Graphviz with the `dot` executable available on `PATH`.
- A browser on the same machine.

## Install and launch

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/flask --app app run --host=127.0.0.1 --port=5015
```

Open `http://<server-ip>:5015`. The development defaults are `admin` and `change-me`. Set `SECRET_KEY`, `ADMIN_USERNAME` and `ADMIN_PASSWORD` before using real system knowledge or enabling network access.

Keep the application bound to `127.0.0.1` unless authentication, strong secrets and an HTTPS reverse proxy are deliberately configured. See [the security model](../security.md).

## Verify service health

`GET /health` is a liveness probe. It returns a small JSON service status when the Flask process can respond and does not require login.

`GET /ready` is the deployment readiness probe. It returns HTTP 200 only when the catalogue database responds, managed storage is writable and Graphviz `dot` is available. A failed dependency returns HTTP 503 with a generic per-check status; internal paths and exception details are not exposed.

Configure process supervisors and container platforms to use `/health` for liveness and `/ready` for readiness. Project and administration pages require an authenticated session.

## Production WSGI launch

The production entry point is `wsgi:application` and the pinned WSGI server is Gunicorn. Before launch, set `SECRET_KEY` to at least 32 random characters, set a non-default `ADMIN_PASSWORD` of at least 12 characters, and explicitly set `DATABASE_URL` and an absolute `DATA_DIR`.

```bash
.venv/bin/gunicorn --bind 0.0.0.0:5015 --workers 2 --timeout 120 wsgi:application
```

The entry point refuses to start when required production settings are absent or unsafe. Keep Gunicorn behind an HTTPS reverse proxy for network-accessible deployments. With SQLite, keep worker count conservative and place both the catalogue and managed data on durable storage that is backed up together.
