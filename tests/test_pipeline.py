"""Pruebas básicas del pipeline (backend mock, sin Demucs pesado)."""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

# Forzar mock antes de importar app
os.environ["SEPARATION_BACKEND"] = "mock"
os.environ["DATA_DIR"] = "/workspace/data"
os.environ["UPLOAD_DIR"] = "/workspace/data/uploads"
os.environ["JOBS_DIR"] = "/workspace/data/jobs"
os.environ["EXPORTS_DIR"] = "/workspace/data/exports"
os.environ["DB_URL"] = "sqlite+aiosqlite:////workspace/data/test_secuencialive.db"

from app.config import get_settings
from app.services.analysis import analyze_audio
from app.services.click import generate_click_track, pad_stem_with_count_in, write_wav
from app.services.export import build_export_zip
from app.services.separation import separate_stems
from app.services.transform import transform_audio_file


@pytest.fixture(scope="module")
def sample_wav(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("audio")
    path = root / "sample.wav"
    sr = 44100
    t = np.linspace(0, 4, sr * 4, endpoint=False)
    y = 0.3 * np.sin(2 * np.pi * 220 * t)
    sf.write(str(path), y, sr)
    return path


def test_analyze_returns_bpm_and_key(sample_wav: Path):
    result = analyze_audio(sample_wav)
    assert result["bpm"] > 0
    assert result["key"]
    assert result["time_signature"] in ("4/4", "3/4")
    assert result["duration_seconds"] == pytest.approx(4.0, abs=0.05)
    assert isinstance(result["sections"], list)
    assert len(result["sections"]) >= 1


def test_mock_separation_creates_stems(sample_wav: Path, tmp_path: Path):
    get_settings.cache_clear()
    os.environ["SEPARATION_BACKEND"] = "mock"
    get_settings.cache_clear()
    stems = separate_stems(sample_wav, tmp_path / "stems", stem_mode="4stems")
    assert set(stems) >= {"vocals", "drums", "bass", "other"}
    for p in stems.values():
        assert p.exists()
        assert p.stat().st_size > 1000


def test_click_and_export_zip(sample_wav: Path, tmp_path: Path):
    get_settings.cache_clear()
    os.environ["SEPARATION_BACKEND"] = "mock"
    get_settings.cache_clear()

    stems = separate_stems(sample_wav, tmp_path / "raw", "4stems")
    analysis = analyze_audio(sample_wav)
    click, count_in = generate_click_track(
        analysis["duration_seconds"], analysis["bpm"], count_in_bars=1
    )
    click_path = tmp_path / "click.wav"
    write_wav(click_path, click)
    assert count_in > 0

    aligned = {}
    for name, path in stems.items():
        dest = tmp_path / "aligned" / f"{name}.wav"
        dest.parent.mkdir(exist_ok=True)
        pad_stem_with_count_in(path, count_in, dest)
        aligned[name] = dest

    analysis["count_in_seconds"] = count_in
    zip_path = tmp_path / "out.zip"
    build_export_zip(
        job_id="test",
        work_dir=tmp_path,
        stems=aligned,
        click_path=click_path,
        guide_path=None,
        analysis=analysis,
        markers=analysis["sections"],
        zip_path=zip_path,
    )
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert "click.wav" in names
        assert "secuencia.json" in names
        assert "marcadores.json" in names
        assert any(n.startswith("stems/") for n in names)
        meta = json.loads(zf.read("secuencia.json"))
        assert meta["bpm"] == analysis["bpm"]


def test_transform_copy_when_no_change(sample_wav: Path, tmp_path: Path):
    dest = tmp_path / "copy.wav"
    transform_audio_file(sample_wav, dest, tempo_ratio=1.0, semitones=0)
    assert dest.exists()


@pytest.mark.asyncio
async def test_health_endpoint():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    get_settings.cache_clear()
    os.environ["SEPARATION_BACKEND"] = "mock"
    get_settings.cache_clear()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # lifespan
        async with app.router.lifespan_context(app):
            res = await client.get("/api/health")
            assert res.status_code == 200
            body = res.json()
            assert body["status"] == "ok"
            assert body["separation_backend"] == "mock"
