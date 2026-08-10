CREATE TABLE knowledge_link (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    document_id INTEGER NOT NULL REFERENCES knowledge_document(id),
    revision_id INTEGER NOT NULL REFERENCES diagram_revision(id),
    target_type VARCHAR(40) NOT NULL,
    target_key VARCHAR(340) NOT NULL,
    created_by VARCHAR(80) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE(document_id, revision_id, target_type, target_key)
);
CREATE INDEX ix_knowledge_link_project_id ON knowledge_link(project_id);
CREATE INDEX ix_knowledge_link_document_id ON knowledge_link(document_id);
