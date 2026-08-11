# Field descriptions and explicit ER terminators

Field descriptions are now authoritative typed catalogue data. The ER language represents them as the reserved field attribute `description="..."`; parsing lifts that value into `ERColumn.description`, revision materialisation stores it in `column_definition.description`, and catalogue edits preserve it through canonical ER regeneration.

Canonical ER output now writes explicit semicolons on every statement line. This avoids the previous newline-termination ambiguity where an inline `//` comment swallowed an automatically appended terminator. Structural brace lines remain un-terminated because they are blocks, not statements.

The catalogue provides description controls for new and existing fields. Graphviz previews display descriptions in a fourth table column. Migration `0021_column_descriptions.sql` adds the persistent column with an empty default for existing catalogue rows.

Regression coverage verifies typed parsing, preview rendering, catalogue persistence, and canonical source output.
