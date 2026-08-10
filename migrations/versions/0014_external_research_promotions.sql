CREATE TABLE external_research_promotion (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    job_id INTEGER NOT NULL REFERENCES external_research_job(id),
    citation_index INTEGER NOT NULL,
    document_id INTEGER NOT NULL UNIQUE REFERENCES knowledge_document(id),
    promoted_by VARCHAR(80) NOT NULL,
    created_at DATETIME NOT NULL,
    UNIQUE (job_id, citation_index)
);
CREATE INDEX ix_external_research_promotion_project_id ON external_research_promotion(project_id);
CREATE INDEX ix_external_research_promotion_job_id ON external_research_promotion(job_id);
CREATE UNIQUE INDEX ix_external_research_promotion_document_id ON external_research_promotion(document_id);
