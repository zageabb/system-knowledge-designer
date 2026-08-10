CREATE TABLE assistant_context_link_new (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    exchange_id INTEGER NOT NULL REFERENCES assistant_exchange(id),
    parent_exchange_id INTEGER NOT NULL REFERENCES assistant_exchange(id),
    created_at DATETIME NOT NULL,
    CONSTRAINT uq_assistant_context_pair UNIQUE (exchange_id, parent_exchange_id)
);

INSERT INTO assistant_context_link_new (id, project_id, exchange_id, parent_exchange_id, created_at)
SELECT id, project_id, exchange_id, parent_exchange_id, created_at
FROM assistant_context_link;

DROP TABLE assistant_context_link;
ALTER TABLE assistant_context_link_new RENAME TO assistant_context_link;

CREATE INDEX ix_assistant_context_link_project_id ON assistant_context_link(project_id);
CREATE INDEX ix_assistant_context_link_exchange_id ON assistant_context_link(exchange_id);
CREATE INDEX ix_assistant_context_link_parent_exchange_id ON assistant_context_link(parent_exchange_id);
