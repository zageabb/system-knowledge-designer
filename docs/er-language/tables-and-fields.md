# Tables, fields and modifiers

A subject area contains `table` and `view` objects. Each field starts with its authored type followed by its physical name.

```erd
erModel Field_Examples {
  dialect "sqlite"
  direction LR
  subjectArea Core {
    table PRODUCT {
      integer product_id PK
      string product_code length=30 unique not_null
      decimal list_price precision=18 scale=2
      string description
    }
    view ACTIVE_PRODUCT {
      integer product_id PK
    }
  }
}
```

Implemented markers:

| Marker | Meaning |
|---|---|
| `PK` | Primary-key participation |
| `FK` | Foreign-key participation/documentation |
| `not_null` | Field is not nullable |
| `unique` | Field has a uniqueness requirement |

Attributes use `name=value`, for example `length=200`, `precision=18`, `scale=2` or `default="Active"`. Attributes and markers may be interleaved. `description="..."` is promoted into the typed catalogue and displayed in diagram previews. Canonical generated source explicitly terminates statement lines with `;`, which also permits a trailing inline comment. Mark `PK` on multiple fields to declare composite primary-key participation; ordered composite relationships are documented separately. Named constraints, indexes, aliases, schemas, tags and computed fields remain planned.
