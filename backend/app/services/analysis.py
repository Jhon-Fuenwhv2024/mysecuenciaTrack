"""Análisis de BPM, compás y tonalidad con librosa (rutas rápidas en CPU)."""

from __future__ import annotations

import logging
from typing import Any

import librosa
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)

MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def analyze_audio(path: str | Any) -> dict[str, Any]:
    settings = get_settings()
    y, sr = librosa.load(str(path), sr=settings.sample_rate, mono=True, duration=settings.max_duration_seconds)
    duration = float(len(y) / sr)

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    bpm = _estimate_bpm(onset_env, sr)
    key, key_confidence = _estimate_key(y, sr)
    time_sig, beats_per_bar = _estimate_time_signature(onset_env, bpm)
    beat_times = _beat_times_from_bpm(duration, bpm)
    sections = _estimate_sections(duration, bpm, beats_per_bar)

    return {
        "bpm": round(float(bpm), 2),
        "key": key,
        "key_confidence": round(float(key_confidence), 3),
        "time_signature": time_sig,
        "beats_per_bar": beats_per_bar,
        "duration_seconds": round(duration, 3),
        "beat_times": [round(float(t), 4) for t in beat_times[:500]],
        "sections": sections,
        "sample_rate": sr,
    }


def _estimate_bpm(onset_env: np.ndarray, sr: int) -> float:
    """Estima tempo con onset envelope (evita beat_track en señales patológicas)."""
    try:
        tempo = librosa.feature.tempo(onset_envelope=onset_env, sr=sr, aggregate=np.median)
        if isinstance(tempo, np.ndarray):
            tempo = float(tempo[0]) if tempo.size else 120.0
        tempo = float(tempo)
    except Exception as exc:  # noqa: BLE001
        logger.warning("tempo falló (%s); usando 120", exc)
        tempo = 120.0
    if not np.isfinite(tempo) or tempo <= 0:
        tempo = 120.0
    while tempo < 70:
        tempo *= 2
    while tempo > 180:
        tempo /= 2
    return tempo


def _beat_times_from_bpm(duration: float, bpm: float) -> list[float]:
    beat_dur = 60.0 / max(bpm, 1.0)
    times = []
    t = 0.0
    while t < duration:
        times.append(t)
        t += beat_dur
    return times


def _estimate_key(y: np.ndarray, sr: int) -> tuple[str, float]:
    chroma = librosa.feature.chroma_stft(y=y, sr=sr, n_fft=2048, hop_length=512)
    chroma_mean = np.mean(chroma, axis=1)
    if float(chroma_mean.sum()) == 0.0:
        return "C major", 0.0

    best_corr = -1.0
    best_key = "C major"
    for i in range(12):
        maj = _safe_corr(np.roll(MAJOR_PROFILE, i), chroma_mean)
        mi = _safe_corr(np.roll(MINOR_PROFILE, i), chroma_mean)
        if maj > best_corr:
            best_corr = maj
            best_key = f"{NOTE_NAMES[i]} major"
        if mi > best_corr:
            best_corr = mi
            best_key = f"{NOTE_NAMES[i]} minor"
    return best_key, max(0.0, best_corr)


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.std() == 0 or b.std() == 0:
        return -1.0
    val = float(np.corrcoef(a, b)[0, 1])
    return -1.0 if np.isnan(val) else val


def _estimate_time_signature(onset_env: np.ndarray, bpm: float) -> tuple[str, int]:
    """Heurística ligera; por defecto 4/4."""
    _ = bpm
    if onset_env.size < 16:
        return "4/4", 4
    # Autocorrelación simple a nivel de frames de onset
    x = onset_env - np.mean(onset_env)
    if np.allclose(x, 0):
        return "4/4", 4
    corr = np.correlate(x, x, mode="full")[len(x) - 1 :]
    # Comparar candidatos de periodo relativo (no crítico para el MVP)
    return "4/4", 4


def _estimate_sections(
    duration: float, bpm: float, beats_per_bar: int
) -> list[dict[str, Any]]:
    """Marcadores editables cada 8 compases (detección estructural ligera)."""
    bar_dur = (60.0 / max(bpm, 1.0)) * beats_per_bar
    labels_cycle = ["intro", "verso", "precoro", "coro", "verso", "coro", "puente", "coro", "outro"]
    step = max(bar_dur * 8, 4.0)
    sections: list[dict[str, Any]] = []
    t = 0.0
    i = 0
    while t < duration - 0.01:
        end = min(t + step, duration)
        label = labels_cycle[i % len(labels_cycle)]
        if i == 0:
            label = "intro"
        if end >= duration - 0.5:
            label = "outro" if i > 0 else label
        sections.append(
            {
                "id": f"sec-{i}",
                "label": label,
                "start": round(t, 3),
                "end": round(end, 3),
                "editable": True,
            }
        )
        t = end
        i += 1
    if not sections:
        sections.append(
            {
                "id": "sec-0",
                "label": "intro",
                "start": 0.0,
                "end": round(duration, 3),
                "editable": True,
            }
        )
    return sections
