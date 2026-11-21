# Combined Amvera image: FastAPI API + prebuilt React SPA in one container.
#
# Amvera runs a single container per project and does not support
# docker-compose, so the frontend is compiled here and served by FastAPI.
# The SPA is built with an empty API base URL, which makes every request
# relative (`/api/v1/...`) and therefore same-origin.

FROM node:22-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_BASE_URL=""
RUN npm run build

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST_DIR=/srv/frontend \
    CERTIFICATES_STORAGE_DIR=/data/certificates

WORKDIR /srv/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend-build /app/dist /srv/frontend
COPY deploy/amvera/entrypoint.sh /usr/local/bin/vector-entrypoint

RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && chmod 0755 /usr/local/bin/vector-entrypoint \
    && mkdir -p /data/certificates \
    && chown -R app:app /srv/backend /srv/frontend /data

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/vector-entrypoint"]
