# Stage 1: build the Next.js frontend as static files.
FROM node:24-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: FastAPI serves the API and the static frontend on one port.
# Headless Chromium renders job pages that need JavaScript; dumb-init reaps its child processes.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JOBFIT_DB_PATH=/data/jobfit.sqlite3 \
    JOBFIT_STATIC_DIR=/app/frontend/out
WORKDIR /app/backend
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps --only-shell chromium \
    && apt-get install -y --no-install-recommends dumb-init \
    && rm -rf /var/lib/apt/lists/*
COPY backend/app ./app
COPY rubric.json /app/rubric.json
COPY .claude/skills/cv-rubric/SKILL.md /app/.claude/skills/cv-rubric/SKILL.md
COPY --from=frontend /frontend/out /app/frontend/out
EXPOSE 8000
ENTRYPOINT ["dumb-init", "--"]
CMD ["uvicorn", "--factory", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
