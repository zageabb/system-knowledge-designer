CREATE TABLE portfolio (
    id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(160) NOT NULL,
    slug VARCHAR(160) NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

ALTER TABLE system_project ADD COLUMN portfolio_id INTEGER REFERENCES portfolio(id);
CREATE INDEX ix_system_project_portfolio_id ON system_project(portfolio_id);
