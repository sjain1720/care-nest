# ---------- Stage 1: build the Angular app into static files ----------
FROM node:20-alpine AS frontend-builder
WORKDIR /build

COPY frontend/package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend/ ./
RUN npm run build -- --configuration production

# ---------- Stage 2: Python runtime that serves API + Angular ----------
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY backend/requirements.txt backend/constraints.txt ./
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

COPY backend/app/ ./app/
COPY --from=frontend-builder /build/dist/frontend/browser/ ./static/

EXPOSE 8080
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
