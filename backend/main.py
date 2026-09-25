"""Legacy API compatibility entrypoint.

The production container runs ``backend.app.main:app``. This module remains
only so existing migration and regression tests can be run during the cutover.
"""
from backend.legacy.main import *  # noqa: F401,F403
