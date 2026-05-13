# Full-stack image for Railway (or any Docker host): Vite SPA + FastAPI.
# Set STATIC_DIR=/app/static in the image; FastAPI serves / and /assets from there.

# --- Frontend build ---
FROM node:20-alpine AS web
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json ./
COPY src ./src
RUN npm run build

# --- Backend ---
FROM python:3.11-slim
WORKDIR /app

COPY python-backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY python-backend/ .

ENV STATIC_DIR=/app/static
COPY --from=web /web/dist ./static/

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
