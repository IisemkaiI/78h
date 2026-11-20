from datetime import UTC, datetime

from app.modules.certificates.pdf import render_certificate_pdf


def test_pdf_generator_creates_landscape_cyrillic_certificate() -> None:
    result = render_certificate_pdf(
        recipient_name="Иван Иванов",
        course_title="Основы разработки на Python",
        completion_date=datetime(2026, 11, 20, tzinfo=UTC),
        issued_at=datetime(2026, 11, 20, 12, tzinfo=UTC),
        certificate_number="EP-2026-0123456789",
        verification_url="https://education.example/certificates/verify/example",
    )

    assert result.startswith(b"%PDF-")
    assert b"/MediaBox [ 0 0 841.8898 595.2756 ]" in result
    assert len(result) > 20_000
