CREATE TABLE assistant_exchange (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    question TEXT NOT NULL,
    answer_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    model_name VARCHAR(160) NOT NULL,
    requested_by VARCHAR(80) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE INDEX ix_assistant_exchange_project_id ON assistant_exchange(project_id);
