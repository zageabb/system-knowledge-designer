# Lexical rules and model declarations

Identifiers start with a letter or underscore and may contain letters, digits, underscores and hyphens. Reserved markers are `PK`, `FK`, `not_null` and `unique`. Model names, subject areas, tables, fields and attribute names use identifiers. Quoted values use JSON-compatible double-quoted strings. Numeric values may be integers or decimals.

Whitespace separates tokens. Newlines terminate declarations in the documented syntax; the parser normalises these into grammar terminators. `#` and `//` begin comments that continue to the end of a line.

Every document has one root:

```erd
erModel Minimal {
  dialect "sqlite"
  direction TB
  subjectArea Core {
    table ITEM {
      integer item_id PK
    }
  }
}
```

`direction` accepts `LR` or `TB`. The current parser records the dialect as a string; dialect-specific type validation is planned.

