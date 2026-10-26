from __future__ import annotations

import json
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_session
from app.models.job import Job, JobStatus
from app.models.user import MembershipTier, User
from app.schemas import JobOut, MarkerUpdate
from app.workers.queue import get_queue

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _songs_limit(user: User | None) -> int:
    settings = get_settings()
    if user is None:
        return settings.free_songs_per_month
    if user.tier == MembershipTier.pro:
        return settings.pro_songs_per_month
    if user.tier == MembershipTier.studio:
        return 9999
    return settings.free_songs_per_month


def _job_to_out(job: Job) -> JobOut:
    markers = json.loads(job.markers_json) if job.markers_json else None
    analysis = json.loads(job.analysis_json) if job.analysis_json else None
    stems = None
    if analysis and "stems" in analysis:
        stems = analysis["stems"]
    elif job.work_dir:
        stems_dir = Path(job.work_dir) / "stems"
        if stems_dir.exists():
            stems = sorted(p.stem for p in stems_dir.glob("*.wav"))
    return JobOut(
        id=job.id,
        status=job.status,
        progress=job.progress,
        message=job.message,
        error=job.error,
        original_filename=job.original_filename,
        bpm=job.bpm,
        key=job.key,
        time_signature=job.time_signature,
        duration_seconds=job.duration_seconds,
        target_bpm=job.target_bpm,
        transpose_semitones=job.transpose_semitones,
        stem_mode=job.stem_mode,
        markers=markers,
        analysis=analysis,
        stems=stems,
        has_export=bool(job.export_zip_path and Path(job.export_zip_path).exists()),
        created_at=job.created_at,
        expires_at=job.expires_at,
    )


@router.post("", response_model=JobOut)
async def create_job(
    file: UploadFile = File(...),
    stem_mode: str = Form("4stems"),
    target_bpm: float | None = Form(None),
    transpose_semitones: int = Form(0),
    count_in_bars: int = Form(1),
    generate_voice_cues: bool = Form(True),
    user_id: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> JobOut:
    settings = get_settings()
    if not file.filename:
        raise HTTPException(400, "Archivo requerido")
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp3", ".wav", ".flac", ".ogg", ".m4a"}:
        raise HTTPException(400, "Formato no soportado. Usa MP3, WAV, FLAC, OGG o M4A.")

    user: User | None = None
    if user_id:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(404, "Usuario no encontrado")
        limit = _songs_limit(user)
        if user.songs_used_this_month >= limit:
            raise HTTPException(
                402,
                f"Límite mensual alcanzado ({limit} canciones). "
                "La membresía Pro estará disponible pronto.",
            )

    job_id = str(uuid.uuid4())
    dest = settings.upload_dir / f"{job_id}{ext}"
    size = 0
    max_bytes = settings.max_upload_mb * 1024 * 1024
    async with aiofiles.open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"Archivo supera {settings.max_upload_mb} MB")
            await out.write(chunk)

    job = Job(
        id=job_id,
        user_id=user.id if user else None,
        status=JobStatus.queued,
        progress=0,
        message="En cola…",
        original_filename=file.filename,
        source_path=str(dest),
        stem_mode=stem_mode if stem_mode in ("4stems", "6stems") else "4stems",
        target_bpm=target_bpm,
        transpose_semitones=transpose_semitones,
        count_in_bars=count_in_bars,
        generate_voice_cues=generate_voice_cues,
    )
    session.add(job)
    if user:
        user.songs_used_this_month += 1
    await session.commit()
    await session.refresh(job)

    await get_queue().enqueue(job_id)
    return _job_to_out(job)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: str, session: AsyncSession = Depends(get_session)) -> JobOut:
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Trabajo no encontrado")
    return _job_to_out(job)


@router.get("", response_model=list[JobOut])
async def list_jobs(
    user_id: str | None = None,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
) -> list[JobOut]:
    q = select(Job).order_by(Job.created_at.desc()).limit(min(limit, 100))
    if user_id:
        q = q.where(Job.user_id == user_id)
    result = await session.execute(q)
    return [_job_to_out(j) for j in result.scalars().all()]


@router.patch("/{job_id}/markers", response_model=JobOut)
async def update_markers(
    job_id: str,
    body: MarkerUpdate,
    session: AsyncSession = Depends(get_session),
) -> JobOut:
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Trabajo no encontrado")
    if job.status not in (JobStatus.ready, JobStatus.failed):
        raise HTTPException(400, "Solo se pueden editar marcadores cuando el trabajo está listo")
    job.markers_json = json.dumps(body.markers, ensure_ascii=False)
    await session.commit()
    await session.refresh(job)
    return _job_to_out(job)


@router.get("/{job_id}/export")
async def download_export(job_id: str, session: AsyncSession = Depends(get_session)):
    job = await session.get(Job, job_id)
    if not job or not job.export_zip_path:
        raise HTTPException(404, "Exportación no disponible")
    path = Path(job.export_zip_path)
    if not path.exists():
        raise HTTPException(410, "El archivo expiró o fue eliminado (retención temporal)")
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"secuencia-{job.original_filename.rsplit('.', 1)[0]}.zip",
    )


@router.get("/{job_id}/stems/{stem_name}")
async def stream_stem(
    job_id: str, stem_name: str, session: AsyncSession = Depends(get_session)
):
    job = await session.get(Job, job_id)
    if not job or not job.work_dir:
        raise HTTPException(404, "Pista no disponible")
    safe = Path(stem_name).name.replace("..", "")
    # stems o click/guia en raíz del work_dir
    candidates = [
        Path(job.work_dir) / "stems" / f"{safe}.wav",
        Path(job.work_dir) / f"{safe}.wav",
    ]
    for path in candidates:
        if path.exists():
            return FileResponse(path, media_type="audio/wav", filename=path.name)
    raise HTTPException(404, f"Stem '{stem_name}' no encontrado")
