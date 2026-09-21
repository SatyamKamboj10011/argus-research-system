"""Deployment entrypoint.

The application lives in :mod:`argus.api`; this module keeps ``uvicorn api:app``
working for existing deployments.
"""

from argus.api import app

__all__ = ["app"]
