import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { downloadCertificate, listMyCertificates, type Certificate } from '../services/certificateService';
import { formatDate } from '../utils/labels';
import '../styles/certificates.css';

export function CertificatesPage() {
  const { token } = useAuth();
  const [items, setItems] = useState<Certificate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    listMyCertificates(token, controller.signal)
      .then(setItems)
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : 'Не удалось загрузить сертификаты.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [token]);

  const handleDownload = async (certificate: Certificate) => {
    if (!token) return;
    setBusyId(certificate.id);
    setError(null);
    try {
      await downloadCertificate(token, certificate);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось скачать сертификат.');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <main className="page certificates-page">
      <header className="page__heading">
        <p className="eyebrow">Ваши достижения</p>
        <h1 className="page__title">Сертификаты</h1>
        <p className="muted">Документы о завершении бесплатных курсов, которые вы прошли.</p>
      </header>
      {error && <p className="alert alert--error" role="alert">{error}</p>}
      {loading && <p className="page__status" role="status">Загружаем сертификаты…</p>}
      {!loading && items.length === 0 && (
        <section className="certificate-empty card">
          <span className="certificate-empty__icon" aria-hidden="true">✳</span>
          <h2>Здесь появятся ваши сертификаты</h2>
          <p className="muted">Завершите уроки и обязательные проверки курса, чтобы получить сертификат.</p>
          <Link className="button button--primary" to="/my-learning">Перейти к обучению</Link>
        </section>
      )}
      {!loading && items.length > 0 && (
        <ul className="certificate-list">
          {items.map((certificate) => (
            <li className="certificate-card card" key={certificate.id}>
              <div className="certificate-card__seal" aria-hidden="true">EP</div>
              <div className="certificate-card__body">
                <p className="eyebrow">Курс завершён</p>
                <h2>{certificate.course_title}</h2>
                <p className="muted">Выдан {formatDate(certificate.issued_at)}</p>
                <p className="certificate-card__number">№ {certificate.certificate_number}</p>
                <div className="certificate-card__actions">
                  <button className="button button--primary button--sm" type="button" disabled={busyId === certificate.id} onClick={() => void handleDownload(certificate)}>
                    {busyId === certificate.id ? 'Готовим PDF…' : 'Скачать PDF'}
                  </button>
                  <Link className="button button--ghost button--sm" to={`/certificates/verify/${encodeURIComponent(certificate.verification_code)}`}>
                    Проверить сертификат
                  </Link>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
