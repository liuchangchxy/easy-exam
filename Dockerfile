# ==============================================================================
# Stage 1: Build Vue 3 Frontend SPA
# ==============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Install dependencies first for efficient layer caching
COPY frontend/package*.json ./
RUN npm install

# Build static production assets into dist/
COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Minimal Python 3.11 Alpine Runtime for fnOS
# ==============================================================================
FROM python:3.11-alpine AS runtime

WORKDIR /app

# Install minimal production dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code and compiled frontend assets
COPY backend/ /app/backend/
COPY --from=frontend-builder /app/frontend/dist/ /app/frontend/dist/

# Runtime environment settings
ENV DATA_DIR=/app/data \
    PORT=3000 \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

# Persistent storage mount point for SQLite database
VOLUME /app/data

# HTTP service port
EXPOSE 3000

# Container healthcheck probe against FastAPI /api/health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:3000/api/health', timeout=3).getcode() == 200 else 1)"

# Start application server with uvicorn
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "3000"]
