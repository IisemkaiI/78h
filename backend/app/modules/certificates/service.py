"""Eligibility checks, transactional issuance and private certificate access."""

from __future__ import annotations

import asyncio
import logging
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.errors import ApiError
from app.modules.certificates.models import Certificate
from app.modules.certificates.pdf import render_certificate_pdf
from app.modules.certificates.storage import CertificateStorage
from app.modules.learning.models.enrollment import Enrollment
from app.modules.learning.services.progress import ProgressService
from app.modules.users.models import User

logger = logging.getLogger(__name__)


class CertificateService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        settings = get_settings()
        self._storage = CertificateStorage(settings.certificates_storage_dir)
        self._frontend_url = settings.public_frontend_url.rstrip("/")

    async def issue(self, user: User, enrollment_id: uuid.UUID) -> Certificate:
        """Reconcile progress and issue exactly once while holding the enrollment lock."""
        enrollment = await self._session.scalar(
            select(Enrollment)
            .options(selectinload(Enrollment.user), selectinload(Enrollment.course))
            .where(Enrollment.id == enrollment_id)
            .with_for_update(of=Enrollment)
        )
        if enrollment is None or enrollment.user_id != user.id:
            raise ApiError(404, "enrollment_not_found", "Enrollment not found.")

        existing = await self._get_for_enrollment(enrollment.id)
        if existing is not None:
            return existing

        progress, _ = await ProgressService(self._session).reconcile(enrollment)
        if not progress.is_completed or progress.completed_at is None:
            # Commit any self-healing completion marker update from the shared
            # progress service, while leaving certificate data untouched.
            await self._session.commit()
            raise ApiError(
                409,
                "course_not_completed",
                "Complete all lessons and required assessments before requesting a certificate.",
                details={
                    "progress_percent": progress.progress_percent,
                    "completed_lessons": progress.completed_lessons,
                    "total_lessons": progress.total_lessons,
                    "completed_required_assessments": progress.completed_required_assessments,
                    "total_required_assessments": progress.total_required_assessments,
                },
            )

        issued_at = datetime.now(UTC)
        certificate_number = f"EP-{issued_at.year}-{uuid.uuid4().hex[:10].upper()}"
        verification_code = secrets.token_urlsafe(32)
        storage_key = self._storage.new_key()
        verification_url = (
            f"{self._frontend_url}/certificates/verify/{verification_code}"
        )
        pdf = await asyncio.to_thread(
            render_certificate_pdf,
            recipient_name=enrollment.user.display_name,
            course_title=enrollment.course.title,
            completion_date=progress.completed_at,
            issued_at=issued_at,
            certificate_number=certificate_number,
            verification_url=verification_url,
            template_version="1",
        )

        file_written = False
        try:
            await self._storage.write(storage_key, pdf)
            file_written = True
            certificate = Certificate(
                id=uuid.uuid4(),
                enrollment_id=enrollment.id,
                recipient_name=enrollment.user.display_name,
                course_title=enrollment.course.title,
                completion_date=progress.completed_at,
                issued_at=issued_at,
                certificate_number=certificate_number,
                verification_code=verification_code,
                template_version="1",
                pdf_storage_key=storage_key,
            )
            self._session.add(certificate)
            await self._session.commit()
            return certificate
        except IntegrityError as exc:
            await self._session.rollback()
            if file_written:
                await self._remove_quietly(storage_key)
            # The unique enrollment constraint is the final idempotency guard
            # in case a writer didn't acquire the same row lock.
            existing = await self._get_for_enrollment(enrollment.id)
            if existing is not None:
                return existing
            logger.exception("Certificate uniqueness conflict for enrollment %s", enrollment.id)
            raise ApiError(
                409,
                "certificate_conflict",
                "The certificate could not be issued because of a uniqueness conflict. Retry the request.",
            ) from exc
        except Exception:
            await self._session.rollback()
            if file_written:
                # A network error during COMMIT can make the outcome unknown.
                # Keep the PDF if the transaction actually committed; deleting
                # it in that case would leave a valid row with a broken download.
                commit_state_known = False
                try:
                    committed = await self._get_for_enrollment(enrollment.id)
                    commit_state_known = True
                except Exception:
                    logger.exception(
                        "Could not determine whether certificate commit succeeded: %s",
                        certificate.id,
                    )
                    committed = None
                if committed is not None and committed.id == certificate.id:
                    return committed
                if committed is None and commit_state_known:
                    await self._remove_quietly(storage_key)
            raise

    async def list_for_user(self, user: User) -> list[Certificate]:
        result = await self._session.scalars(
            select(Certificate)
            .join(Enrollment, Enrollment.id == Certificate.enrollment_id)
            .where(Enrollment.user_id == user.id)
            .order_by(Certificate.issued_at.desc(), Certificate.id.desc())
        )
        return list(result.all())

    async def get_owned(self, user: User, certificate_id: uuid.UUID) -> Certificate:
        certificate = await self._session.scalar(
            select(Certificate)
            .join(Enrollment, Enrollment.id == Certificate.enrollment_id)
            .where(Certificate.id == certificate_id, Enrollment.user_id == user.id)
        )
        if certificate is None:
            raise ApiError(404, "certificate_not_found", "Certificate not found.")
        return certificate

    async def get_pdf(self, user: User, certificate_id: uuid.UUID) -> tuple[Certificate, bytes]:
        certificate = await self.get_owned(user, certificate_id)
        try:
            content = await self._storage.read(certificate.pdf_storage_key)
        except FileNotFoundError as exc:
            logger.error("PDF missing for certificate %s", certificate.id)
            raise ApiError(404, "certificate_file_missing", "Certificate PDF is unavailable.") from exc
        return certificate, content

    async def verify(self, verification_code: str) -> Certificate:
        certificate = await self._session.scalar(
            select(Certificate).where(Certificate.verification_code == verification_code)
        )
        if certificate is None:
            raise ApiError(404, "certificate_not_found", "Certificate not found.")
        return certificate

    async def _get_for_enrollment(self, enrollment_id: uuid.UUID) -> Certificate | None:
        return await self._session.scalar(
            select(Certificate).where(Certificate.enrollment_id == enrollment_id)
        )

    async def _remove_quietly(self, key: str) -> None:
        try:
            await self._storage.remove(key)
        except (OSError, ValueError):
            logger.exception("Could not clean up certificate file %s", key)
