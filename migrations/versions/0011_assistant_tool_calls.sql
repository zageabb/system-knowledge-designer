CREATE TABLE assistant_tool_call (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES system_project(id),
    tool_name VARCHAR(100) NOT NULL,
    input_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    status VARCHAR(30) NOT NULL,
    requested_by VARCHAR(80) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE INDEX ix_assistant_tool_call_project_id ON assistant_tool_call(project_id);
