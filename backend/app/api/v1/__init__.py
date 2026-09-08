"""
Version 1 API routers.

`api_router` aggregates every router the application exposes. `app/main.py`
mounts only this object, so adding a resource is a single import here rather
than a change to the application module.

All 46 endpoints from the migration inventory are now served by this backend.
The Spring backend remains running as the parity reference until Phase 10.
"""
from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    challenges,
    documents,
    evaluations,
    knowledge_base,
    matching,
    notifications,
    pilots,
    proposals,
    startups,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(challenges.router)
api_router.include_router(startups.router)
api_router.include_router(matching.router)
api_router.include_router(proposals.router)
api_router.include_router(documents.router)
api_router.include_router(evaluations.router)
api_router.include_router(pilots.router)
api_router.include_router(knowledge_base.router)
api_router.include_router(notifications.router)
api_router.include_router(admin.router)

__all__ = ["api_router"]
