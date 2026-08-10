CREATE TABLE external_research_job (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    original_query TEXT NOT NULL,
    outbound_query VARCHAR(500) NOT NULL,
    provider VARCHAR(80) NOT NULL,
    status VARCHAR(30) NOT NULL,
    results_json TEXT NOT NULL,
    error TEXT NOT NULL,
    requested_by VARCHAR(80) NOT NULL,
    sent_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE INDEX ix_external_research_job_project_id ON external_research_job(project_id);
