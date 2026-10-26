# SecuenciaLive

MVP web para generar **secuencias / multitracks** orientadas a músicos en vivo (estilo flujo Moises.ai, pero enfocado en Ableton Live, Playback de MultiTracks.com o Prime).

**Dueño:** Jhon Fuentes (Colombia) — estudiante de Ingeniería de Software.  
**Repo:** [github.com/Jhon-Fuenwhv2024/mysecuenciaTrack](https://github.com/Jhon-Fuenwhv2024/mysecuenciaTrack)

Interfaz y documentación en **español**.

## Qué hace este MVP

1. Subes una canción (MP3/WAV y otros formatos comunes).
2. Separación de pistas con **Demucs** (`htdemucs`; opción `6stems` → `htdemucs_6s` si está disponible).
3. Análisis automático: **BPM**, **compás** y **tonalidad** (librosa).
4. Generación de secuencia: **click/metrónomo**, **conteo de entrada**, cues de guía por sección y marcadores editables.
5. Transposición y cambio de tempo (Rubber Band CLI si está instalado; si no, librosa).
6. Exportación **ZIP** con stems WAV alineados desde 0, click, guía, `secuencia.json`, marcadores y una **plantilla Ableton** básica.
7. Reproductor web multitrack (mute / solo / volumen + click).

Estructura lista para **membresías** (usuarios Free/Pro/Studio y límite de canciones/mes) **sin pagos** integrados.

## Stack

| Capa | Tecnología |
|------|------------|
| API | Python 3.12, FastAPI, SQLAlchemy (SQLite), cola asyncio |
| Audio | Demucs, librosa, soundfile, ffmpeg, rubberband-cli (opcional) |
| Frontend | Vue 3 + Vite + TypeScript |
| Empaquetado | Docker Compose |

## Requisitos

- Python 3.12+, Node 20+, ffmpeg
- Opcional: Docker / Docker Compose
- Opcional GPU NVIDIA + CUDA para Demucs en producción
- Opcional: `rubberband-cli` para time-stretch/pitch de alta calidad

## Arranque rápido (sin Docker)

```bash
# 1) Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SEPARATION_BACKEND=mock   # o demucs
export PYTHONPATH=/workspace/backend
uvicorn app.main:app --host 0.0.0.0 --port 8765

# 2) Frontend (otra terminal)
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 3847
```

Abre [http://127.0.0.1:3847](http://127.0.0.1:3847).

### Con Demucs real (CPU)

```bash
export SEPARATION_BACKEND=demucs
export DEMUCS_MODEL=htdemucs
export USE_GPU=false
```

La primera ejecución descarga el modelo. En CPU un tema de 3–4 minutos puede tardar **mucho**; para el MVP usa clips cortos o `SEPARATION_BACKEND=mock`.

## Docker Compose

```bash
cp .env.example .env
# SEPARATION_BACKEND=mock  # recomendado la primera vez
docker compose up --build
```

- Web: http://127.0.0.1:3847  
- API: http://127.0.0.1:8765/api/health  

### GPU en producción

1. Usa una imagen base CUDA (p. ej. `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime`) en `backend/Dockerfile`.
2. Instala el wheel de torch CUDA correspondiente.
3. Define `USE_GPU=true` y monta el runtime NVIDIA:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

4. En el host: drivers NVIDIA + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

## Pruebas

```bash
cd /workspace
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
export SEPARATION_BACKEND=mock
python scripts/generate_sample.py
pytest -q
```

El E2E sube un WAV corto, separa (mock), analiza, genera click y descarga el ZIP.

## Audio de prueba punta a punta (API)

```bash
# con el API en marcha (mock o demucs)
curl -F "file=@samples/prueba_120bpm_C.wav" \
  -F "stem_mode=4stems" \
  -F "count_in_bars=1" \
  http://127.0.0.1:8765/api/jobs
# consulta GET /api/jobs/{id} hasta status=ready
# descarga GET /api/jobs/{id}/export
```

## Costos estimados de servidor con GPU (orden de magnitud, 2025–2026)

| Opción | Uso típico | Costo aprox. |
|--------|------------|--------------|
| Cloud GPU spot (T4 / L4) | Demucs bajo demanda | USD 0.20–0.80 / h |
| VPS CPU 8 vCPU / 16 GB | Cola lenta, pocos usuarios | USD 20–60 / mes |
| Instancia dedicada 1× RTX 4090 (proveedor GPU) | Producción pequeña | USD 200–450 / mes |
| Serverless GPU (RunPod / Vast / etc.) | Picos | Pagos por minuto; suele salir más barato al inicio |

Un tema de ~4 min en **T4** suele separarse en el orden de **decenas de segundos**; en CPU puede irse a **varios minutos**. Empieza con cola + un worker GPU y retención corta de archivos.

## Derechos de autor y retención

- Solo sube material del que tengas derechos (obra propia, licencia o autorización).
- **No se almacenan canciones de forma permanente:** el original se borra tras procesar; resultados (ZIP/stems) expiran según `RETENTION_HOURS` (por defecto 24 h).
- El usuario es responsable del uso de las secuencias en ensayos, cultos o conciertos.
- Ver también `/terminos` en la app y `GET /api/terminos`.

## Membresías (preparado, sin pagos)

Modelo `User` con tiers `free` / `pro` / `studio` y contador `songs_used_this_month`. Límites por defecto: Free 3/mes, Pro 50/mes. Los pagos (Stripe u otro) quedan fuera de este MVP.

## Estructura del repo

```
backend/app/          API FastAPI + servicios de audio + cola
frontend/src/         Vue 3 (upload, progreso, player, marcadores)
tests/                Unitarias + E2E mock
samples/              Audio de prueba
docker-compose.yml
```

## Pendiente / mejoras naturales

- TTS hablado real para cues (“intro”, “verso”, “coro”) — hoy son tonos sincronizados.
- Plantilla Ableton más rica (clips pre-cargados); el `.als` actual fija tempo y nombres de pista.
- Redis/RQ o Celery si hay varios workers.
- Auth completa + Stripe para Pro.
- Mejor detección de secciones (madmom/Essentia) y compases compuestos.

## Licencia de uso del proyecto

Código del MVP para desarrollo y demostración académica/comercial de Jhon Fuentes. El audio que suban los usuarios sigue siendo responsabilidad de cada usuario.
