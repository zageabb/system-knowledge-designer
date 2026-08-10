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

Composite relationships use ordered, equal-length field lists. Each pair is retained as a linked relationship edge in the typed model and renderer:

```erd
erModel Composite_Relationship {
  subjectArea Core {
    table PARENT {
      integer tenant_id PK
      integer parent_id PK
    }
    table CHILD {
      integer tenant_id PK FK
      integer parent_id PK FK
    }
    relationship (CHILD.tenant_id, CHILD.parent_id) -> (PARENT.tenant_id, PARENT.parent_id) {
      cardinality many-to-one
      label "composite parent"
    }
  }
}
```

Semantic validation rejects unequal composite field counts, duplicate tables, duplicate fields, missing referenced tables and missing referenced fields. Syntax diagnostics include line and column where Lark provides them. Cross-project aliases and managed include validation remain planned.
