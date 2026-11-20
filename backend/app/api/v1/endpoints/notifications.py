from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep
from app.core.errors import ApiError
from app.modules.auth.dependencies import require_permissions
from app.modules.notifications.schemas import NotificationPage, NotificationRead
from app.modules.notifications.service import NotificationService
from app.modules.users.models import User
from app.modules.users.rbac import PermissionCode as P

router = APIRouter(prefix="/notifications", tags=["Notifications"])
Reader = Annotated[User, Depends(require_permissions(P.NOTIFICATIONS_READ_OWN))]
Updater = Annotated[User, Depends(require_permissions(P.NOTIFICATIONS_UPDATE_OWN))]


@router.get("/me", response_model=NotificationPage)
async def list_notifications(user: Reader, session: SessionDep, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), unread_only: bool = False):
    return await NotificationService(session).list(user.id, page, page_size, unread_only)


@router.get("/unread-count")
async def unread_count(user: Reader, session: SessionDep):
    return {"unread_count": await NotificationService(session).unread_count(user.id)}


@router.patch("/{notification_id}/read", response_model=NotificationRead)
async def mark_read(notification_id: uuid.UUID, user: Updater, session: SessionDep):
    notification = await NotificationService(session).mark_read(user.id, notification_id)
    if notification is None:
        raise ApiError(404, "notification_not_found", "Notification not found.")
    return notification


@router.post("/read-all")
async def mark_all_read(user: Updater, session: SessionDep):
    return {"updated": await NotificationService(session).mark_all_read(user.id)}
