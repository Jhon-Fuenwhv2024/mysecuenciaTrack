"""Separación de stems con Demucs (htdemucs / htdemucs_6s) o mock para pruebas."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from app.config import get_settings

logger = logging.getLogger(__name__)

STEM_NAMES_4 = ("vocals", "drums", "bass", "other")
STEM_NAMES_6 = ("vocals", "drums", "bass", "guitar", "piano", "other")


def separate_stems(
    source_path: Path,
    output_dir: Path,
    stem_mode: str = "4stems",
) -> dict[str, Path]:
    """
    Separa la mezcla en stems WAV alineados.
    Retorna mapa nombre -> ruta.
    """
    settings = get_settings()
    output_dir.mkdir(parents=True, exist_ok=True)

    if settings.separation_backend == "mock":
        return _mock_separate(source_path, output_dir, stem_mode)

    model = "htdemucs_6s" if stem_mode == "6stems" else settings.demucs_model
    return _demucs_separate(source_path, output_dir, model, stem_mode)


def _demucs_separate(
    source_path: Path,
    output_dir: Path,
    model: str,
    stem_mode: str,
) -> dict[str, Path]:
    settings = get_settings()
    demucs_out = output_dir / "_demucs"
    demucs_out.mkdir(parents=True, exist_ok=True)

    device = "cuda" if settings.use_gpu else "cpu"
    cmd = [
        sys.executable,
        "-m",
        "demucs",
        "-n",
        model,
        "-d",
        device,
        "--out",
        str(demucs_out),
        str(source_path),
    ]
    logger.info("Ejecutando Demucs: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("Demucs stderr: %s", result.stderr)
        # Fallback a 4 stems si 6s no está disponible
        if model == "htdemucs_6s":
            logger.warning("htdemucs_6s falló; reintentando con htdemucs (4 stems)")
            return _demucs_separate(source_path, output_dir, "htdemucs", "4stems")
        raise RuntimeError(f"Demucs falló: {result.stderr[-2000:]}")

    # demucs escribe en out/<model>/<track_name>/*.wav
    track_dirs = list(demucs_out.rglob("*.wav"))
    if not track_dirs:
        raise RuntimeError("Demucs no produjo archivos WAV")

    stems_dir = track_dirs[0].parent
    expected = STEM_NAMES_6 if stem_mode == "6stems" and model == "htdemucs_6s" else STEM_NAMES_4
    result_map: dict[str, Path] = {}
    for name in expected:
        src = stems_dir / f"{name}.wav"
        if not src.exists():
            # algunos modelos usan nombres distintos
            alt = list(stems_dir.glob(f"{name}*.wav"))
            if not alt:
                continue
            src = alt[0]
        dest = output_dir / f"{name}.wav"
        shutil.copy2(src, dest)
        result_map[name] = dest

    if not result_map:
        raise RuntimeError(f"No se encontraron stems en {stems_dir}")

    # Limpiar carpeta intermedia de demucs para ahorrar disco
    shutil.rmtree(demucs_out, ignore_errors=True)
    return result_map


def _mock_separate(
    source_path: Path,
    output_dir: Path,
    stem_mode: str,
) -> dict[str, Path]:
    """
    Separación sintética para CI: filtra bandas de frecuencia para simular stems.
    No es calidad de producción; solo asegura el flujo E2E.
    """
    import librosa

    settings = get_settings()
    y, sr = librosa.load(str(source_path), sr=settings.sample_rate, mono=False)
    if y.ndim == 1:
        y = np.stack([y, y])

    # Usar canal mono para filtros
    mono = librosa.to_mono(y)
    names = STEM_NAMES_6 if stem_mode == "6stems" else STEM_NAMES_4

    # Bandas aproximadas
    bands = {
        "bass": (20, 250),
        "drums": (60, 8000),
        "vocals": (200, 5000),
        "guitar": (80, 5000),
        "piano": (100, 6000),
        "other": (100, 12000),
    }

    result: dict[str, Path] = {}
    for name in names:
        low, high = bands.get(name, (80, 8000))
        filtered = _bandpass(mono, sr, low, high)
        # Estéreo simple
        stereo = np.stack([filtered * 0.9, filtered * 0.85])
        path = output_dir / f"{name}.wav"
        sf.write(str(path), stereo.T, sr, subtype="PCM_16")
        result[name] = path
    return result


def _bandpass(y: np.ndarray, sr: int, low: float, high: float) -> np.ndarray:
    from scipy.signal import butter, sosfilt

    nyq = sr / 2
    low_n = max(low / nyq, 0.001)
    high_n = min(high / nyq, 0.999)
    if low_n >= high_n:
        return y * 0.3
    sos = butter(2, [low_n, high_n], btype="band", output="sos")
    return sosfilt(sos, y).astype(np.float32)
