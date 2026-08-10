# Grammar versioning and planned syntax

The core language is experimental and currently has no explicit source-level version declaration. Before the first stable release, the grammar will receive a version policy and compatibility fixtures.

Planned additions include schemas, composite keys/relationships, constraints, indexes, descriptions, aliases, notes, tags, styling, cross-project references, includes and layout hints. Planned examples are not included as executable `.erd` blocks until the parser supports them.

Breaking syntax changes require migration notes, old-version fixtures and actionable diagnostics. Deprecations must remain accepted for a documented transition period where practical.

