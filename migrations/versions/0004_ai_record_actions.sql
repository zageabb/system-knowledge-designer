CREATE TABLE ai_action (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    dataset_id INTEGER REFERENCES sample_dataset(id),
    action_type VARCHAR(80) NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'proposed',
    payload_json TEXT NOT NULL,
    result_json TEXT NOT NULL DEFAULT '{}',
    requested_by VARCHAR(80) NOT NULL DEFAULT 'user',
    confirmed_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE INDEX ix_ai_action_project_id ON ai_action(project_id);

