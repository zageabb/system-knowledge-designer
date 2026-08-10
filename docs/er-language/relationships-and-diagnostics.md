# Relationships and diagnostics

Relationships connect exact fields rather than table outlines.

```erd
erModel Relationship_Example {
  dialect "sqlite"
  direction LR
  subjectArea Core {
    table PARENT {
      integer parent_id PK
    }
    table CHILD {
      integer child_id PK
      integer parent_id FK not_null
    }
    relationship CHILD.parent_id -> PARENT.parent_id {
      cardinality many-to-one
      label "belongs to"
      on_delete restrict
    }
  }
}
```

The core grammar accepts arbitrary named relationship attributes with identifier, number or quoted-string values. `cardinality` defaults to `many-to-one`; `label` defaults to empty. The current renderer displays the label and retains other attributes in the intermediate model.

Semantic validation rejects duplicate tables, duplicate fields, missing referenced tables and missing referenced fields. Syntax diagnostics include line and column where Lark provides them. Composite relationships, cross-project aliases and include validation are planned.

