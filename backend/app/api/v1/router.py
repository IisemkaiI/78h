"""Versioned API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import assessments, auth, catalog, courses, learning, system, users

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(catalog.router)
api_router.include_router(courses.router)
api_router.include_router(learning.router)
api_router.include_router(assessments.router)
