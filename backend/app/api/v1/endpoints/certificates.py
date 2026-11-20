"""Private certificate operations and public authenticity verification."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import SessionDep
from app.modules.auth.dependencies import require_permissions
from app.modules.certificates.schemas import (
    CertificateIssueRequest,
    CertificateRead,
    PublicCertificateRead,
)
from app.modules.certificates.service import CertificateService
from app.modules.users.models import User
from app.modules.users.rbac import PermissionCode as P

router = APIRouter(prefix="/certificates", tags=["Certificates"])
Issuer = Annotated[User, Depends(require_permissions(P.CERTIFICATES_ISSUE_SELF))]
Reader = Annotated[User, Depends(require_permissions(P.CERTIFICATES_READ_SELF))]


@router.post("/issue", response_model=CertificateRead, status_code=status.HTTP_201_CREATED)
async def issue_certificate(payload: CertificateIssueRequest, user: Issuer, session: SessionDep):
    certificate = await CertificateService(session).issue(user, payload.enrollment_id)
    return certificate


@router.get("/me", response_model=list[CertificateRead])
async def list_my_certificates(user: Reader, session: SessionDep):
    return await CertificateService(session).list_for_user(user)


@router.get("/{certificate_id}/download")
async def download_certificate(certificate_id: uuid.UUID, user: Reader, session: SessionDep):
    certificate, content = await CertificateService(session).get_pdf(user, certificate_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{certificate.certificate_number}.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/verify/{verification_code}", response_model=PublicCertificateRead)
async def verify_certificate(verification_code: str, session: SessionDep):
    certificate = await CertificateService(session).verify(verification_code)
    return PublicCertificateRead(
        valid=True,
        recipient_name=certificate.recipient_name,
        course_title=certificate.course_title,
        certificate_number=certificate.certificate_number,
        issued_at=certificate.issued_at,
    )
