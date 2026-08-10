CREATE TABLE evidence_record (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    query VARCHAR(500) NOT NULL,
    source_filter VARCHAR(40) NOT NULL,
    model_revision_id INTEGER REFERENCES diagram_revision(id),
    evidence_json TEXT NOT NULL,
    created_by VARCHAR(80) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE INDEX ix_evidence_record_project_id ON evidence_record(project_id);
