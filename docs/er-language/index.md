# ER language reference

**Language status:** experimental core  
**Recommended extension:** `.erd`

This is the normative reference for syntax currently accepted by the grammar in `services/er_language/parser.py`. The parser grammar and typed intermediate model remain authoritative if prose and implementation differ.

## Core example

```erd
erModel Procurement {
  dialect "sqlite"
  direction LR
  subjectArea Buying {
    table SUPPLIER {
      integer supplier_id PK
      string supplier_name length=200 not_null
    }
    table PURCHASE_ORDER {
      integer purchase_order_id PK
      integer supplier_id FK not_null
      decimal order_value precision=18 scale=2
    }
    relationship PURCHASE_ORDER.supplier_id -> SUPPLIER.supplier_id {
      cardinality many-to-one
      label "placed with"
    }
  }
}
```

## Reference sections

- [Lexical rules and declarations](lexical-and-model.md)
- [Tables, fields and modifiers](tables-and-fields.md)
- [Relationships and validation](relationships-and-diagnostics.md)
- [Grammar versioning and planned syntax](versioning.md)

