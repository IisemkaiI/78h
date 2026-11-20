import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { verifyCertificate, type PublicCertificate } from '../services/certificateService';
import { formatDate } from '../utils/labels';
import '../styles/certificates.css';

export function CertificateVerificationPage() {
  const { verificationCode = '' } = useParams();
  const [certificate, setCertificate] = useState<PublicCertificate | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    verifyCertificate(verificationCode, controller.signal)
      .then(setCertificate)
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        const status = typeof caught === 'object' && caught !== null && 'status' in caught
          ? (caught as { status?: number }).status : null;
        if (status === 404) setNotFound(true);
        else setError(true);
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [verificationCode]);

  return (
    <main className="page certificates-page verification-page">
      <header className="page__heading">
        <p className="eyebrow">Публичная проверка</p>
        <h1 className="page__title">Подлинность сертификата</h1>
      </header>
      {loading && <p className="page__status" role="status">Проверяем сертификат…</p>}
      {!loading && certificate && (
        <section className="verification-card card" aria-labelledby="verification-title">
          <div className="verification-card__status"><span aria-hidden="true">✓</span> Сертификат действителен</div>
          <h2 id="verification-title">{certificate.course_title}</h2>
          <dl>
            <div><dt>Получатель</dt><dd>{certificate.recipient_name}</dd></div>
            <div><dt>Номер</dt><dd>{certificate.certificate_number}</dd></div>
            <div><dt>Дата выдачи</dt><dd>{formatDate(certificate.issued_at)}</dd></div>
          </dl>
        </section>
      )}
      {!loading && notFound && <section className="certificate-empty card"><h2>Сертификат не найден</h2><p className="muted">Проверьте ссылку или номер сертификата.</p></section>}
      {!loading && error && <p className="alert alert--error" role="alert">Не удалось проверить сертификат. Попробуйте позже.</p>}
      <Link className="text-link" to="/">На главную</Link>
    </main>
  );
}
