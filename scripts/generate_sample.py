#!/usr/bin/env python3
"""Genera un WAV de prueba corto (~8 s) con tempo y tonalidad conocidos."""

from pathlib import Path

import numpy as np
import soundfile as sf

OUT = Path(__file__).resolve().parents[1] / "samples" / "prueba_120bpm_C.wav"
SR = 44100
BPM = 120.0
DURATION = 8.0
BEAT = 60.0 / BPM


def main() -> None:
    n = int(SR * DURATION)
    t = np.arange(n) / SR
    # Tono C major: C3, E3, G3 + kick en negros
    freqs = [130.81, 164.81, 196.0]
    tone = sum(0.2 * np.sin(2 * np.pi * f * t) for f in freqs)
    # Envelope suave
    tone *= 0.5 + 0.5 * np.sin(2 * np.pi * (BPM / 60) * t / 4)

    kick = np.zeros(n)
    for i in range(int(DURATION / BEAT)):
        idx = int(i * BEAT * SR)
        length = int(0.08 * SR)
        if idx + length >= n:
            break
        env = np.exp(-np.linspace(0, 8, length))
        kick[idx : idx + length] += 0.7 * np.sin(2 * np.pi * 60 * np.linspace(0, 0.08, length)) * env

    # "Voz" sintética más aguda
    voice = 0.15 * np.sin(2 * np.pi * 440 * t) * (0.3 + 0.7 * (np.sin(2 * np.pi * 2 * t) > 0))

    mix = np.clip(tone + kick + voice, -1, 1).astype(np.float32)
    stereo = np.stack([mix, mix * 0.98], axis=1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(OUT), stereo, SR, subtype="PCM_16")
    print(f"Escrito {OUT} ({DURATION}s, {BPM} BPM, C)")


if __name__ == "__main__":
    main()
