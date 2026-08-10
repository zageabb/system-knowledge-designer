CREATE TABLE cross_project_attachment (id INTEGER NOT NULL PRIMARY KEY, consumer_project_id INTEGER NOT NULL REFERENCES system_project(id), source_project_id INTEGER NOT NULL REFERENCES system_project(id), document_id INTEGER NOT NULL REFERENCES knowledge_document(id), created_by VARCHAR(80) NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, UNIQUE(consumer_project_id,document_id));
CREATE INDEX ix_cross_project_attachment_consumer_project_id ON cross_project_attachment(consumer_project_id);
CREATE INDEX ix_cross_project_attachment_source_project_id ON cross_project_attachment(source_project_id);
CREATE INDEX ix_cross_project_attachment_document_id ON cross_project_attachment(document_id);
