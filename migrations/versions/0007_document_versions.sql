CREATE TABLE document_version (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    document_id INTEGER NOT NULL UNIQUE REFERENCES knowledge_document(id),
    family_id VARCHAR(36) NOT NULL,
    version_number INTEGER NOT NULL,
    predecessor_document_id INTEGER REFERENCES knowledge_document(id),
    UNIQUE(family_id, version_number)
);
CREATE INDEX ix_document_version_project_id ON document_version(project_id);
CREATE UNIQUE INDEX ix_document_version_document_id ON document_version(document_id);
CREATE INDEX ix_document_version_family_id ON document_version(family_id);
