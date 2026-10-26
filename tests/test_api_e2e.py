"""E2E: sube audio de prueba, procesa (mock) y descarga ZIP."""

from __future__ import annotations

import asyncio
import os
import zipfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

os.environ["SEPARATION_BACKEND"] = "mock"
os.environ["DATA_DIR"] = "/workspace/data"
os.environ["UPLOAD_DIR"] = "/workspace/data/uploads"
os.environ["JOBS_DIR"] = "/workspace/data/jobs"
os.environ["EXPORTS_DIR"] = "/workspace/data/exports"
os.environ["DB_URL"] = "sqlite+aiosqlite:////workspace/data/test_e2e.db"

from app.config import get_settings


@pytest.fixture
def short_wav(tmp_path: Path) -> Path:
    path = tmp_path / "e2e.wav"
    sr = 44100
    t = np.linspace(0, 3, sr * 3, endpoint=False)
    y = 0.25 * np.sin(2 * np.pi * 196 * t) + 0.2 * np.sin(2 * np.pi * 98 * t)
    # pulsos rítmicos
    for i in range(0, 3 * 2):
        idx = int(i * 0.5 * sr)
        if idx < len(y):
            y[idx : idx + 1000] += 0.4
    sf.write(str(path), np.clip(y, -1, 1), sr)
    return path


@pytest.mark.asyncio
async def test_upload_process_export(short_wav: Path):
    get_settings.cache_clear()
    os.environ["SEPARATION_BACKEND"] = "mock"
    get_settings.cache_clear()

    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            with short_wav.open("rb") as f:
                res = await client.post(
                    "/api/jobs",
                    files={"file": ("e2e.wav", f, "audio/wav")},
                    data={
                        "stem_mode": "4stems",
                        "count_in_bars": "1",
                        "transpose_semitones": "0",
                        "generate_voice_cues": "true",
                    },
                )
            assert res.status_code == 200, res.text
            job = res.json()
            job_id = job["id"]

            # Esperar procesamiento
            ready = None
            for _ in range(60):
                await asyncio.sleep(0.25)
                st = await client.get(f"/api/jobs/{job_id}")
                assert st.status_code == 200
                ready = st.json()
                if ready["status"] in ("ready", "failed"):
                    break

            assert ready is not None
            assert ready["status"] == "ready", ready.get("error")
            assert ready["bpm"]
            assert ready["has_export"] is True

            export = await client.get(f"/api/jobs/{job_id}/export")
            assert export.status_code == 200
            zip_path = Path("/workspace/data/exports") / f"{job_id}_test.zip"
            zip_path.write_bytes(export.content)
            with zipfile.ZipFile(zip_path) as zf:
                assert "click.wav" in zf.namelist()
                assert "secuencia.json" in zf.namelist()
