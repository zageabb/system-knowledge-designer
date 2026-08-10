CREATE TABLE assistant_context_link (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    exchange_id INTEGER NOT NULL UNIQUE REFERENCES assistant_exchange(id),
    parent_exchange_id INTEGER NOT NULL REFERENCES assistant_exchange(id),
    created_at DATETIME NOT NULL
);
CREATE INDEX ix_assistant_context_link_project_id ON assistant_context_link(project_id);
CREATE UNIQUE INDEX ix_assistant_context_link_exchange_id ON assistant_context_link(exchange_id);
CREATE INDEX ix_assistant_context_link_parent_exchange_id ON assistant_context_link(parent_exchange_id);
