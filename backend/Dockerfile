FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    rubberband-cli \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# CPU torch por defecto; para GPU ver README (imagen CUDA)
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PYTHONUNBUFFERED=1 \
    SEPARATION_BACKEND=demucs \
    USE_GPU=false \
    DATA_DIR=/data \
    UPLOAD_DIR=/data/uploads \
    JOBS_DIR=/data/jobs \
    EXPORTS_DIR=/data/exports \
    DB_URL=sqlite+aiosqlite:////data/secuencialive.db

RUN mkdir -p /data/uploads /data/jobs /data/exports

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
