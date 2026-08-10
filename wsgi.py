from __future__ import annotations

import os

from app import create_app
from services.deployment import validate_production_environment


validate_production_environment(os.environ)
application = create_app()
