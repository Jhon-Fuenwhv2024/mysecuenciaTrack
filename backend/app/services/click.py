"""Generación de click/metrónomo, conteo de entrada y cues de guía hablados."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from app.config import get_settings


def generate_click_track(
    duration_seconds: float,
    bpm: float,
    beats_per_bar: int = 4,
    count_in_bars: int = 1,
    sample_rate: int | None = None,
) -> tuple[np.ndarray, float]:
    """
    Genera click estéreo. Retorna (audio, offset_count_in_seconds).
    El offset es la duración del conteo; los stems deben alinearse con silencio
    al inicio o el click incluye conteo antes del beat 1 de la canción.
    """
    settings = get_settings()
    sr = sample_rate or settings.sample_rate
    beat_dur = 60.0 / max(bpm, 1.0)
    count_in_beats = max(0, count_in_bars) * beats_per_bar
    count_in_seconds = count_in_beats * beat_dur
    total_seconds = count_in_seconds + duration_seconds
    n = int(total_seconds * sr)
    audio = np.zeros((2, n), dtype=np.float32)

    total_beats = int(np.ceil(total_seconds / beat_dur)) + 1
    for i in range(total_beats):
        t = i * beat_dur
        idx = int(t * sr)
        if idx >= n:
            break
        is_downbeat = i % beats_per_bar == 0
        # Conteos de entrada: clicks más agudos
        in_count_in = i < count_in_beats
        freq = 1500.0 if is_downbeat else (1200.0 if in_count_in else 1000.0)
        amp = 0.55 if is_downbeat else 0.35
        click = _synth_click(sr, freq=freq, amp=amp)
        end = min(idx + len(click), n)
        audio[0, idx:end] += click[: end - idx]
        audio[1, idx:end] += click[: end - idx] * 0.95

    peak = np.max(np.abs(audio)) or 1.0
    if peak > 0.95:
        audio *= 0.95 / peak
    return audio, count_in_seconds


def generate_guide_track(
    duration_seconds: float,
    sections: list[dict[str, Any]],
    count_in_seconds: float = 0.0,
    sample_rate: int | None = None,
) -> np.ndarray:
    """
    Cues de guía: tonos cortos + forma de onda tipo 'beep' en cada sección.
    (TTS real queda pendiente; estos cues son audibles y sincronizados.)
    """
    settings = get_settings()
    sr = sample_rate or settings.sample_rate
    total = duration_seconds + count_in_seconds
    n = int(total * sr)
    audio = np.zeros((2, n), dtype=np.float32)

    label_freqs = {
        "intro": 440.0,
        "verso": 523.25,
        "precoro": 587.33,
        "coro": 659.25,
        "puente": 392.0,
        "outro": 349.23,
    }

    for sec in sections:
        label = str(sec.get("label", "marcador")).lower()
        start = float(sec.get("start", 0)) + count_in_seconds
        freq = label_freqs.get(label, 480.0)
        cue = _synth_cue(sr, freq=freq, duration=0.35)
        idx = int(start * sr)
        end = min(idx + len(cue), n)
        if idx >= n or end <= idx:
            continue
        audio[0, idx:end] += cue[: end - idx]
        audio[1, idx:end] += cue[: end - idx] * 0.9

    peak = np.max(np.abs(audio)) or 1.0
    if peak > 0.8:
        audio *= 0.8 / peak
    return audio


def pad_stem_with_count_in(
    stem_path: Path,
    count_in_seconds: float,
    output_path: Path,
    sample_rate: int | None = None,
) -> Path:
    """Alinea un stem desde 0 insertando silencio del conteo."""
    settings = get_settings()
    sr = sample_rate or settings.sample_rate
    data, file_sr = sf.read(str(stem_path), always_2d=True)
    if file_sr != sr:
        import librosa

        # soundfile: (samples, channels)
        reshaped = data.T
        resampled = librosa.resample(reshaped, orig_sr=file_sr, target_sr=sr)
        data = resampled.T
        file_sr = sr

    pad = int(count_in_seconds * file_sr)
    silence = np.zeros((pad, data.shape[1]), dtype=np.float32)
    out = np.concatenate([silence, data.astype(np.float32)], axis=0)
    sf.write(str(output_path), out, file_sr, subtype="PCM_16")
    return output_path


def write_wav(path: Path, audio: np.ndarray, sample_rate: int | None = None) -> Path:
    settings = get_settings()
    sr = sample_rate or settings.sample_rate
    # audio shape (2, n) -> (n, 2)
    if audio.ndim == 2 and audio.shape[0] == 2:
        to_write = audio.T
    else:
        to_write = audio
    sf.write(str(path), to_write, sr, subtype="PCM_16")
    return path


def _synth_click(sr: int, freq: float = 1000.0, amp: float = 0.4) -> np.ndarray:
    dur = 0.012
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    env = np.exp(-t * 180)
    return (amp * np.sin(2 * np.pi * freq * t) * env).astype(np.float32)


def _synth_cue(sr: int, freq: float, duration: float = 0.3) -> np.ndarray:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    env = np.concatenate(
        [
            np.linspace(0, 1, max(1, int(0.02 * sr))),
            np.ones(max(0, len(t) - int(0.08 * sr))),
            np.linspace(1, 0, max(1, int(0.06 * sr))),
        ]
    )
    env = env[: len(t)]
    if len(env) < len(t):
        env = np.pad(env, (0, len(t) - len(env)))
    return (0.25 * np.sin(2 * np.pi * freq * t) * env).astype(np.float32)
