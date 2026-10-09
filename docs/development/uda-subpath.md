# UDA application prefix integration

Status: IN PROGRESS

The registered System Knowledge Designer service preserves direct LAN root access while trusting one isolated UDA/Caddy forwarding hop for `X-Forwarded-Prefix`. Base URLs and Flask-generated links resolve within the mounted path. Authentication and CSRF protections stay enabled.

Evidence: `tests/test_uda_subpath.py`, `.github/workflows/uda-tests.yml`.

- [ ] CI passes and change merges to `main`
- [ ] Verify UDA sign-in/out, navigation, CSRF forms, and static assets in the live proxy
- [ ] Keep backend reachable only from trusted proxy; do not enable public route before auth tests
