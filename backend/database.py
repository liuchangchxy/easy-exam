"""Compatibility export for the legacy test/migration surface.

Production uses ``backend.app.infrastructure.db`` instead.
"""
from backend.legacy.database import *  # noqa: F401,F403
