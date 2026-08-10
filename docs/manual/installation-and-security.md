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

Open `http://127.0.0.1:5015`. The development defaults are `admin` and `change-me`. Set `SECRET_KEY`, `ADMIN_USERNAME` and `ADMIN_PASSWORD` before using real system knowledge or enabling network access.

Keep the application bound to `127.0.0.1` unless authentication, strong secrets and an HTTPS reverse proxy are deliberately configured. See [the security model](../security.md).

## Verify service health

`GET /health` returns a small JSON service status and does not require login. Project and administration pages require an authenticated session.

