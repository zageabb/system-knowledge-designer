# Managed includes

An include is a project-scoped catalogue record containing a self-contained ER model. It is referenced by name at the top level of another model:

```erd
erModel Included_Example {
  include "shared core"
  subjectArea Local {
    table REPORT {
      integer report_id PK
    }
  }
}
```

Create includes from the Workbench's **Managed ER includes** section. Names are normalized case-insensitively with repeated whitespace collapsed and are unique within one project. They are identifiers, never filesystem paths; authored content cannot select a server or sandbox path.

Resolution is recursive and occurs before semantic validation. Included tables and relationships are ordered before local declarations. Missing names, duplicate objects after merging, nesting beyond eight levels, expansion beyond twenty includes and circular chains are rejected with actionable diagnostics.

Saving a revision persists the resolved typed model. Later deletion of an include can make the authored source impossible to resolve again, but it cannot change the historical revision's catalogue, render, sandbox or model hash.

Layout hints remain planned.
