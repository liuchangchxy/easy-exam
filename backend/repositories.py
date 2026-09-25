"""Compatibility export for the retired repository implementation.

Production uses ``backend.app.infrastructure.db.repositories``.
"""
from backend.legacy.repositories import *  # noqa: F401,F403
