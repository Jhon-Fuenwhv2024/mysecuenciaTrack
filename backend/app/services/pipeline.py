"""Orquestación del pipeline: separar → analizar → transformar → click → exportar."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.job import Job, JobStatus
from app.services.analysis import analyze_audio
from app.services.click import (
    generate_click_track,
    generate_guide_track,
    pad_stem_with_count_in,
    write_wav,
)
from app.services.export import build_export_zip
from app.services.separation import separate_stems
from app.services.transform import transform_stems

logger = logging.getLogger(__name__)


async def run_job(session: AsyncSession, job_id: str) -> None:
    settings = get_settings()
    job = await session.get(Job, job_id)
    if not job:
        logger.error("Job %s no encontrado", job_id)
        return

    work_dir = settings.jobs_dir / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    job.work_dir = str(work_dir)
    job.expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.retention_hours)

    try:
        await _set(session, job, JobStatus.separating, 5, "Separando pistas con IA…")
        stems_raw_dir = work_dir / "stems_raw"
        stems = separate_stems(
            Path(job.source_path),
            stems_raw_dir,
            stem_mode=job.stem_mode,
        )

        await _set(session, job, JobStatus.analyzing, 35, "Analizando BPM, compás y tonalidad…")
        analysis = analyze_audio(job.source_path)
        job.bpm = analysis["bpm"]
        job.key = analysis["key"]
        job.time_signature = analysis["time_signature"]
        job.duration_seconds = analysis["duration_seconds"]
        markers = analysis.get("sections", [])
        job.markers_json = json.dumps(markers, ensure_ascii=False)

        # Transformaciones
        tempo_ratio = 1.0
        target_bpm = job.target_bpm or analysis["bpm"]
        if job.target_bpm and analysis["bpm"]:
            tempo_ratio = float(job.target_bpm) / float(analysis["bpm"])

        await _set(session, job, JobStatus.transforming, 50, "Aplicando tempo/tono…")
        stems_tx_dir = work_dir / "stems_tx"
        stems = transform_stems(
            stems,
            stems_tx_dir,
            tempo_ratio=tempo_ratio,
            semitones=job.transpose_semitones or 0,
        )

        # Si cambió el tempo, ajustar duración y BPM reportados
        effective_bpm = float(target_bpm)
        effective_duration = float(analysis["duration_seconds"]) / tempo_ratio
        # Ajustar marcadores al nuevo tempo
        if abs(tempo_ratio - 1.0) >= 1e-4:
            markers = [
                {
                    **m,
                    "start": round(float(m["start"]) / tempo_ratio, 3),
                    "end": round(float(m["end"]) / tempo_ratio, 3),
                }
                for m in markers
            ]
            # Transponer nombre de tonalidad (aproximado)
            if job.transpose_semitones:
                analysis["key"] = _transpose_key_label(
                    analysis["key"], job.transpose_semitones
                )
                job.key = analysis["key"]

        analysis["bpm"] = round(effective_bpm, 2)
        analysis["duration_seconds"] = round(effective_duration, 3)
        analysis["target_bpm"] = effective_bpm
        analysis["transpose_semitones"] = job.transpose_semitones or 0
        job.bpm = analysis["bpm"]
        job.duration_seconds = analysis["duration_seconds"]
        job.markers_json = json.dumps(markers, ensure_ascii=False)

        await _set(session, job, JobStatus.generating, 70, "Generando click y guía…")
        beats_per_bar = int(analysis.get("beats_per_bar") or 4)
        click_audio, count_in = generate_click_track(
            effective_duration,
            effective_bpm,
            beats_per_bar=beats_per_bar,
            count_in_bars=job.count_in_bars,
        )
        analysis["count_in_seconds"] = count_in
        click_path = work_dir / "click.wav"
        write_wav(click_path, click_audio)

        guide_path = work_dir / "guia.wav"
        if job.generate_voice_cues:
            guide = generate_guide_track(
                effective_duration, markers, count_in_seconds=count_in
            )
            write_wav(guide_path, guide)
        else:
            guide_path = None

        # Alinear stems con conteo
        stems_final: dict[str, Path] = {}
        aligned_dir = work_dir / "stems"
        aligned_dir.mkdir(exist_ok=True)
        for name, path in stems.items():
            dest = aligned_dir / f"{name}.wav"
            pad_stem_with_count_in(path, count_in, dest)
            stems_final[name] = dest

        await _set(session, job, JobStatus.exporting, 90, "Empaquetando ZIP…")
        zip_path = settings.exports_dir / f"{job_id}.zip"
        build_export_zip(
            job_id=job_id,
            work_dir=work_dir,
            stems=stems_final,
            click_path=click_path,
            guide_path=guide_path,
            analysis=analysis,
            markers=markers,
            zip_path=zip_path,
        )
        job.export_zip_path = str(zip_path)
        job.analysis_json = json.dumps(analysis, ensure_ascii=False)

        # Borrar fuente original (no almacenamiento permanente)
        if job.source_path:
            Path(job.source_path).unlink(missing_ok=True)
            job.source_path = None

        # Limpiar stems intermedios pesados
        shutil.rmtree(stems_raw_dir, ignore_errors=True)
        shutil.rmtree(stems_tx_dir, ignore_errors=True)

        await _set(session, job, JobStatus.ready, 100, "Secuencia lista")
        logger.info("Job %s listo", job_id)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Job %s falló", job_id)
        job.status = JobStatus.failed
        job.error = str(exc)[:2000]
        job.message = "Error en el procesamiento"
        job.progress = 0
        await session.commit()


async def _set(
    session: AsyncSession, job: Job, status: JobStatus, progress: int, message: str
) -> None:
    job.status = status
    job.progress = progress
    job.message = message
    await session.commit()


def _transpose_key_label(key: str, semitones: int) -> str:
    notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    parts = key.split()
    if not parts:
        return key
    root = parts[0]
    mode = parts[1] if len(parts) > 1 else "major"
    if root not in notes:
        return key
    idx = (notes.index(root) + semitones) % 12
    return f"{notes[idx]} {mode}"


async def cleanup_expired(session: AsyncSession) -> int:
    """Elimina archivos de trabajos expirados (cumplimiento de retención)."""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Job).where(Job.expires_at.is_not(None), Job.expires_at < now)
    )
    jobs = result.scalars().all()
    removed = 0
    for job in jobs:
        if job.work_dir:
            shutil.rmtree(job.work_dir, ignore_errors=True)
        if job.export_zip_path:
            Path(job.export_zip_path).unlink(missing_ok=True)
        job.status = JobStatus.expired
        job.export_zip_path = None
        job.work_dir = None
        removed += 1
    await session.commit()
    return removed
