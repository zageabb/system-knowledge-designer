CREATE TABLE external_research_job_event (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    job_id INTEGER NOT NULL REFERENCES external_research_job(id),
    event_type VARCHAR(40) NOT NULL,
    related_job_id INTEGER REFERENCES external_research_job(id),
    actor VARCHAR(80) NOT NULL,
    detail TEXT NOT NULL,
    created_at DATETIME NOT NULL
);
CREATE INDEX ix_external_research_job_event_project_id ON external_research_job_event(project_id);
CREATE INDEX ix_external_research_job_event_job_id ON external_research_job_event(job_id);
