CREATE TABLE knowledge_document (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    title VARCHAR(240) NOT NULL,
    original_filename VARCHAR(240) NOT NULL,
    media_type VARCHAR(120) NOT NULL,
    managed_path VARCHAR(500) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    provenance VARCHAR(80) NOT NULL DEFAULT 'uploaded',
    classification VARCHAR(80) NOT NULL DEFAULT 'internal',
    status VARCHAR(40) NOT NULL DEFAULT 'indexed',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE INDEX ix_knowledge_document_project_id ON knowledge_document(project_id);
CREATE TABLE document_chunk (
    id INTEGER NOT NULL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES knowledge_document(id),
    position INTEGER NOT NULL,
    locator VARCHAR(240) NOT NULL,
    text TEXT NOT NULL,
    UNIQUE(document_id, position)
);
CREATE INDEX ix_document_chunk_document_id ON document_chunk(document_id);
CREATE VIRTUAL TABLE document_chunk_fts USING fts5(chunk_id UNINDEXED, project_id UNINDEXED, title, locator, content);
