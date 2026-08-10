-- Control settings persistence.
CREATE TABLE app_setting (
    key VARCHAR(120) NOT NULL PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

