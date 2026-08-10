# Repository working agreement

- The structured catalogue is authoritative; ER source is parsed into it and render artefacts are derived.
- Keep parsing independent of Flask and Graphviz.
- Keep SQL generation, deterministic validation, and sandbox execution separate.
- Never execute user-authored shell commands or use user-supplied sandbox paths.
- Material AI changes remain proposals until a user confirms them.
- Add migrations and tests with every persistent capability.
- Record phase evidence in `docs/development/`.

