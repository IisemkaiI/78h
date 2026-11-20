"""Certificate request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CertificateIssueRequest(BaseModel):
    enrollment_id: uuid.UUID


class CertificateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recipient_name: str
    course_title: str
    completion_date: datetime
    issued_at: datetime
    certificate_number: str
    verification_code: str
    template_version: str


class PublicCertificateRead(BaseModel):
    valid: bool
    recipient_name: str
    course_title: str
    certificate_number: str
    issued_at: datetime
