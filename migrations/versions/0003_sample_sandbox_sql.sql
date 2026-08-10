CREATE TABLE sample_dataset (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    name VARCHAR(160) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    provenance VARCHAR(80) NOT NULL DEFAULT 'synthetic',
    classification VARCHAR(80) NOT NULL DEFAULT 'non-sensitive',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE INDEX ix_sample_dataset_project_id ON sample_dataset(project_id);

CREATE TABLE sample_row_definition (
    id INTEGER NOT NULL PRIMARY KEY,
    dataset_id INTEGER NOT NULL REFERENCES sample_dataset(id),
    table_name VARCHAR(160) NOT NULL,
    position INTEGER NOT NULL,
    values_json TEXT NOT NULL,
    UNIQUE(dataset_id, table_name, position)
);
CREATE INDEX ix_sample_row_definition_dataset_id ON sample_row_definition(dataset_id);

CREATE TABLE sandbox_build (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    dataset_id INTEGER NOT NULL REFERENCES sample_dataset(id),
    revision_id INTEGER NOT NULL REFERENCES diagram_revision(id),
    status VARCHAR(24) NOT NULL,
    managed_path VARCHAR(500) NOT NULL,
    build_hash VARCHAR(64) NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    error TEXT NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL,
    completed_at DATETIME
);
CREATE INDEX ix_sandbox_build_project_id ON sandbox_build(project_id);

CREATE TABLE sql_execution (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    sandbox_build_id INTEGER NOT NULL REFERENCES sandbox_build(id),
    statement TEXT NOT NULL,
    referenced_objects_json TEXT NOT NULL DEFAULT '[]',
    status VARCHAR(24) NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    runtime_ms FLOAT NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL
);
CREATE INDEX ix_sql_execution_project_id ON sql_execution(project_id);
