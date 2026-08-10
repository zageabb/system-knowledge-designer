from __future__ import annotations

from pathlib import Path
from typing import Mapping


class DeploymentConfigurationError(RuntimeError):
    pass


def validate_production_environment(environment: Mapping[str, str]) -> None:
    errors = []
    secret = environment.get("SECRET_KEY", "")
    password = environment.get("ADMIN_PASSWORD", "")
    database_url = environment.get("DATABASE_URL", "")
    data_dir = environment.get("DATA_DIR", "")

    if len(secret) < 32 or secret == "local-development-only-change-me":
        errors.append("SECRET_KEY must be a non-default value of at least 32 characters")
    if len(password) < 12 or password == "change-me":
        errors.append("ADMIN_PASSWORD must be a non-default value of at least 12 characters")
    if not database_url:
        errors.append("DATABASE_URL must be set explicitly")
    if not data_dir or not Path(data_dir).is_absolute():
        errors.append("DATA_DIR must be set to an absolute path")
    if errors:
        raise DeploymentConfigurationError("Production configuration is invalid: " + "; ".join(errors) + ".")
