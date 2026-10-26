"""
Use for migrations through the Supabase session pooler (port 5432):

    python manage.py migrate --settings=config.settings_migrate

Requires MIGRATION_DATABASE_URL in .env. Falls back to DATABASE_URL if unset.
"""
import os

import dj_database_url

from .settings import *  # noqa: F401,F403
from .settings import DATABASES

_url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
DATABASES["default"] = dj_database_url.parse(_url, conn_max_age=0, ssl_require=True)
