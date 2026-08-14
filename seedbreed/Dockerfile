# ---- frontend build ----
FROM node:20-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

# ---- final image: backend + nginx, one container (Unraid-friendly) ----
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx supervisor libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app

COPY --from=frontend-build /app/dist /usr/share/nginx/html
RUN rm -f /etc/nginx/sites-enabled/default
COPY nginx.conf /etc/nginx/sites-enabled/seedbreed.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

ENV SEEDBREED_DATA_DIR=/data
ENV SEEDBREED_PHOTOS_DIR=/photos
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /data /photos

EXPOSE 80

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
