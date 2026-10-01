"""Compatibility exports for the retired prototype services.

New production code lives under ``backend.app``.
"""
from backend.legacy.services import *  # noqa: F401,F403
from backend.legacy import services as _legacy_services

__all__ = list(_legacy_services.__all__)
for _k in _legacy_services.__all__:
    globals()[_k] = getattr(_legacy_services, _k)
