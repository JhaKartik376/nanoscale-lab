# Full-stack single container: builds the React frontend and serves it from the
# FastAPI backend (same origin -> the Claude chat tutor and all APIs work).
# Used by render.yaml / any Docker host.

# --- stage 1: build the frontend (same-origin API calls) ---
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_URL=""
RUN npm run build

# --- stage 2: backend + bundled static frontend ---
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist ./static
EXPOSE 8000
# hosts (Render, Fly, …) inject $PORT; default to 8000 locally
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
