# Codex control API

The **Settings** page contains both local Ollama defaults and the Codex control section. The versioned control API enables permissioned application inspection and bounded control from Codex and is disabled by default.

## Configure

1. Set a long random `CODEX_CONTROL_TOKEN` in the application environment.
2. Restart the Flask process.
3. Sign in as an administrator and open **Control Settings**.
4. Enable the Codex control API.

Send the token as `Authorization: Bearer TOKEN`. Turning the setting off blocks all endpoints immediately.

The initial API can inspect projects/revisions, validate ER source, create projects and create draft revisions. It cannot approve revisions, run shell commands, choose filesystem paths or execute arbitrary SQL. See the [overall design](../overall-design.md) for the endpoint table and governance rules.
