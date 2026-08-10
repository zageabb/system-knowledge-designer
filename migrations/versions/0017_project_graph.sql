CREATE TABLE project_link (id INTEGER NOT NULL PRIMARY KEY, source_project_id INTEGER NOT NULL REFERENCES system_project(id), target_project_id INTEGER NOT NULL REFERENCES system_project(id), relationship_type VARCHAR(40) NOT NULL, label VARCHAR(200) NOT NULL, created_by VARCHAR(80) NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, UNIQUE(source_project_id,target_project_id,relationship_type));
CREATE INDEX ix_project_link_source_project_id ON project_link(source_project_id);
CREATE INDEX ix_project_link_target_project_id ON project_link(target_project_id);
CREATE TABLE project_alias (id INTEGER NOT NULL PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES system_project(id), alias VARCHAR(160) NOT NULL, normalized_alias VARCHAR(160) NOT NULL UNIQUE, trusted BOOLEAN NOT NULL, created_by VARCHAR(80) NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL);
CREATE INDEX ix_project_alias_project_id ON project_alias(project_id);
CREATE UNIQUE INDEX ix_project_alias_normalized_alias ON project_alias(normalized_alias);
CREATE TABLE project_integrity_scan (id INTEGER NOT NULL PRIMARY KEY, status VARCHAR(30) NOT NULL, results_json TEXT NOT NULL, issue_count INTEGER NOT NULL, requested_by VARCHAR(80) NOT NULL, created_at DATETIME NOT NULL);
