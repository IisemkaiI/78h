import { API_BASE_URL, apiRequest } from './apiClient';

export interface Certificate {
  id: string;
  recipient_name: string;
  course_title: string;
  completion_date: string;
  issued_at: string;
  certificate_number: string;
  verification_code: string;
  template_version: string;
}

export interface PublicCertificate {
  valid: boolean;
  recipient_name: string;
  course_title: string;
  certificate_number: string;
  issued_at: string;
}

const PREFIX = '/api/v1/certificates';

export const listMyCertificates = (token: string, signal?: AbortSignal) =>
  apiRequest<Certificate[]>(`${PREFIX}/me`, { token, signal });

export const issueCertificate = (token: string, enrollmentId: string) =>
  apiRequest<Certificate>(`${PREFIX}/issue`, {
    method: 'POST',
    body: { enrollment_id: enrollmentId },
    token,
  });

export const verifyCertificate = (code: string, signal?: AbortSignal) =>
  apiRequest<PublicCertificate>(`${PREFIX}/verify/${encodeURIComponent(code)}`, { signal });

export async function downloadCertificate(token: string, certificate: Certificate): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${PREFIX}/${certificate.id}/download`, {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/pdf' },
  });
  if (!response.ok) {
    let message = 'Не удалось скачать сертификат.';
    try {
      const payload: unknown = await response.json();
      if (typeof payload === 'object' && payload !== null && 'error' in payload) {
        const error = (payload as { error?: { message?: string } }).error;
        if (typeof error?.message === 'string') message = error.message;
      }
    } catch {
      // Use the safe fallback for unexpected/non-JSON errors.
    }
    throw new Error(message);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = `${certificate.certificate_number}.pdf`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
