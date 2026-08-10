from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path

from models import DiagramRevision, SampleDataset, SandboxBuild, utcnow
from services.er_language import parse_er_source
from services.sample_data import validate_row


TYPE_MAP = {"integer": "INTEGER", "int": "INTEGER", "bigint": "INTEGER", "smallint": "INTEGER", "decimal": "REAL", "numeric": "REAL", "real": "REAL", "float": "REAL", "double": "REAL", "boolean": "INTEGER", "bool": "INTEGER", "blob": "BLOB"}


def build_sandbox(project, revision: DiagramRevision, dataset: SampleDataset, data_dir: Path) -> SandboxBuild:
    if project.active_revision_id != revision.id or revision.status != "approved":
        raise ValueError("A sandbox can only be built from the active approved revision.")
    model = parse_er_source(revision.source)
    table_order = {table.name.casefold(): position for position, table in enumerate(model.tables)}
    canonical_rows = [{"table": row.table_name, "position": row.position, "values": json.loads(row.values_json)} for row in sorted(dataset.rows, key=lambda r: (table_order.get(r.table_name.casefold(), len(table_order)), r.position, r.table_name.casefold()))]
    build_hash = hashlib.sha256((revision.model_hash + json.dumps(canonical_rows, sort_keys=True)).encode()).hexdigest()
    sandbox_dir = Path(data_dir).resolve() / str(project.id) / "sandboxes"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    final_path = sandbox_dir / f"{build_hash}.sqlite"
    temp_path = sandbox_dir / f".{build_hash}.building"
    build = SandboxBuild(project_id=project.id, dataset_id=dataset.id, revision_id=revision.id, managed_path=str(final_path), build_hash=build_hash)
    try:
        if temp_path.exists(): temp_path.unlink()
        connection = sqlite3.connect(temp_path)
        # Load in deterministic source order, then validate all relationships in
        # one pass so child rows may appear before their referenced parents.
        connection.execute("PRAGMA foreign_keys=OFF")
        for table in model.tables:
            definitions = []
            primary = [c for c in table.columns if "PK" in c.markers]
            for column in table.columns:
                sql_type = TYPE_MAP.get(column.data_type.casefold(), "TEXT")
                parts = [quote_identifier(column.name), sql_type]
                if not column.nullable: parts.append("NOT NULL")
                if len(primary) == 1 and column is primary[0]: parts.append("PRIMARY KEY")
                if "unique" in column.markers: parts.append("UNIQUE")
                definitions.append(" ".join(parts))
            if len(primary) > 1: definitions.append("PRIMARY KEY (" + ", ".join(quote_identifier(c.name) for c in primary) + ")")
            for relationship in model.relationships:
                if relationship.source_table.casefold() == table.name.casefold():
                    definitions.append(
                        f"FOREIGN KEY ({quote_identifier(relationship.source_column)}) REFERENCES "
                        f"{quote_identifier(relationship.target_table)} ({quote_identifier(relationship.target_column)})"
                    )
            connection.execute(f"CREATE TABLE {quote_identifier(table.name)} ({', '.join(definitions)})")
        count = 0
        for item in canonical_rows:
            values = validate_row(model, item["table"], item["values"])
            names = list(values)
            connection.execute(f"INSERT INTO {quote_identifier(item['table'])} ({', '.join(quote_identifier(n) for n in names)}) VALUES ({', '.join('?' for _ in names)})", [values[n] for n in names])
            count += 1
        integrity_failures = connection.execute("PRAGMA foreign_key_check").fetchall()
        if integrity_failures: raise ValueError(f"Foreign-key validation failed for {len(integrity_failures)} row(s).")
        connection.commit(); connection.close()
        os.replace(temp_path, final_path)
        build.status = "completed"; build.row_count = count; build.completed_at = utcnow()
    except Exception as exc:
        try: connection.close()
        except Exception: pass
        if temp_path.exists(): temp_path.unlink()
        build.status = "failed"; build.error = str(exc); build.completed_at = utcnow()
    return build


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
