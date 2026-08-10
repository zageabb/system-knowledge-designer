from __future__ import annotations

import os
import shutil
from pathlib import Path

from sqlalchemy import text


def readiness_report(*, session, data_dir: Path, executable_finder=shutil.which) -> tuple[dict, int]:
    checks: dict[str, dict[str, str]] = {}
    try:
        session.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception:
        checks["database"] = {"status": "failed", "detail": "catalogue database is unavailable"}

    managed_root = Path(data_dir)
    storage_ready = managed_root.is_dir() and os.access(managed_root, os.W_OK | os.X_OK)
    checks["managed_storage"] = ({"status": "ok"} if storage_ready else {"status": "failed", "detail": "managed storage is not writable"})

    graphviz_ready = executable_finder("dot") is not None
    checks["graphviz"] = ({"status": "ok"} if graphviz_ready else {"status": "failed", "detail": "Graphviz dot is unavailable"})

    ready = all(check["status"] == "ok" for check in checks.values())
    return {"status": "ready" if ready else "not_ready", "service": "system-knowledge-designer", "checks": checks}, 200 if ready else 503
