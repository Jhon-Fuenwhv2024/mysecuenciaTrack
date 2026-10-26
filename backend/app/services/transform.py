"""Transposición y cambio de tempo sin distorsión (Rubber Band si hay CLI; si no, librosa)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from app.config import get_settings

logger = logging.getLogger(__name__)


def has_rubberband() -> bool:
    return shutil.which("rubberband") is not None


def transform_audio_file(
    source: Path,
    dest: Path,
    *,
    tempo_ratio: float = 1.0,
    semitones: int = 0,
) -> Path:
    """
    Cambia tempo y/o tono.
    tempo_ratio = target_bpm / source_bpm (1.0 = sin cambio).
    """
    if abs(tempo_ratio - 1.0) < 1e-4 and semitones == 0:
        if source.resolve() != dest.resolve():
            shutil.copy2(source, dest)
        return dest

    if has_rubberband():
        return _rubberband_transform(source, dest, tempo_ratio=tempo_ratio, semitones=semitones)
    return _librosa_transform(source, dest, tempo_ratio=tempo_ratio, semitones=semitones)


def _rubberband_transform(
    source: Path,
    dest: Path,
    *,
    tempo_ratio: float,
    semitones: int,
) -> Path:
    """Usa rubberband-cli (algoritmo de alta calidad)."""
    cmd = ["rubberband", "-q"]
    if abs(tempo_ratio - 1.0) >= 1e-4:
        cmd += ["--time", f"{1.0 / tempo_ratio:.6f}"]
    if semitones:
        cmd += ["--pitch", str(semitones)]
    cmd += [str(source), str(dest)]
    logger.info("Rubber Band: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("Rubber Band falló (%s); usando librosa", result.stderr[-500:])
        return _librosa_transform(source, dest, tempo_ratio=tempo_ratio, semitones=semitones)
    return dest


def _librosa_transform(
    source: Path,
    dest: Path,
    *,
    tempo_ratio: float,
    semitones: int,
) -> Path:
    settings = get_settings()
    y, sr = librosa.load(str(source), sr=settings.sample_rate, mono=False)
    if y.ndim == 1:
        y = y[np.newaxis, :]

    channels = []
    for ch in y:
        out = ch
        if abs(tempo_ratio - 1.0) >= 1e-4:
            out = librosa.effects.time_stretch(out, rate=tempo_ratio)
        if semitones:
            out = librosa.effects.pitch_shift(out, sr=sr, n_steps=semitones)
        channels.append(out)

    # Alinear longitudes
    min_len = min(len(c) for c in channels)
    stereo = np.stack([c[:min_len] for c in channels], axis=1)
    sf.write(str(dest), stereo, sr, subtype="PCM_16")
    return dest


def transform_stems(
    stem_paths: dict[str, Path],
    output_dir: Path,
    *,
    tempo_ratio: float = 1.0,
    semitones: int = 0,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    for name, path in stem_paths.items():
        dest = output_dir / f"{name}.wav"
        transform_audio_file(path, dest, tempo_ratio=tempo_ratio, semitones=semitones)
        result[name] = dest
    return result
