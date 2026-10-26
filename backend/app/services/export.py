"""Exportación ZIP: stems, click, guía, metadata y plantilla Ableton básica."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring


def build_export_zip(
    job_id: str,
    work_dir: Path,
    stems: dict[str, Path],
    click_path: Path,
    guide_path: Path | None,
    analysis: dict[str, Any],
    markers: list[dict[str, Any]],
    zip_path: Path,
) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "app": "SecuenciaLive",
        "job_id": job_id,
        "bpm": analysis.get("bpm"),
        "key": analysis.get("key"),
        "time_signature": analysis.get("time_signature"),
        "duration_seconds": analysis.get("duration_seconds"),
        "count_in_seconds": analysis.get("count_in_seconds", 0),
        "transpose_semitones": analysis.get("transpose_semitones", 0),
        "target_bpm": analysis.get("target_bpm"),
        "stems": list(stems.keys()),
        "markers": markers,
        "nota": (
            "Los archivos están alineados desde el sample 0. "
            "El click incluye conteo de entrada; los stems tienen silencio equivalente."
        ),
    }

    meta_path = work_dir / "secuencia.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    markers_path = work_dir / "marcadores.json"
    markers_path.write_text(json.dumps(markers, ensure_ascii=False, indent=2), encoding="utf-8")

    # Cue sheet simple (útil en DAWs)
    cue_path = work_dir / "marcadores.cue"
    cue_path.write_text(_to_cue_sheet(markers, analysis), encoding="utf-8")

    # Plantilla Ableton Live (ALS = gzip XML). Generamos un .als mínimo con tempo.
    als_path = work_dir / "SecuenciaLive_plantilla.als"
    _write_ableton_template(als_path, analysis, list(stems.keys()))

    readme = work_dir / "LEEME.txt"
    readme.write_text(
        _readme_export(analysis, list(stems.keys())),
        encoding="utf-8",
    )

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, path in stems.items():
            zf.write(path, arcname=f"stems/{name}.wav")
        zf.write(click_path, arcname="click.wav")
        if guide_path and guide_path.exists():
            zf.write(guide_path, arcname="guia.wav")
        zf.write(meta_path, arcname="secuencia.json")
        zf.write(markers_path, arcname="marcadores.json")
        zf.write(cue_path, arcname="marcadores.cue")
        zf.write(als_path, arcname="ableton/SecuenciaLive_plantilla.als")
        zf.write(readme, arcname="LEEME.txt")

    return zip_path


def _to_cue_sheet(markers: list[dict[str, Any]], analysis: dict[str, Any]) -> str:
    lines = [
        'TITLE "SecuenciaLive"',
        f'PERFORMER "BPM {analysis.get("bpm")} | {analysis.get("key")}"',
        'FILE "mix.wav" WAVE',
    ]
    for i, m in enumerate(markers, start=1):
        start = float(m.get("start", 0))
        mins = int(start // 60)
        secs = start - mins * 60
        frames = int((secs % 1) * 75)
        sec_i = int(secs)
        lines.append(f"  TRACK {i:02d} AUDIO")
        lines.append(f'    TITLE "{m.get("label", "marcador")}"')
        lines.append(f"    INDEX 01 {mins:02d}:{sec_i:02d}:{frames:02d}")
    return "\n".join(lines) + "\n"


def _write_ableton_template(
    path: Path, analysis: dict[str, Any], stem_names: list[str]
) -> None:
    """
    Escribe un .als mínimo (XML gzip) con tempo y pistas vacías nombradas.
    Ableton puede abrir plantillas simples; el usuario arrastra los WAV del ZIP.
    """
    import gzip

    bpm = float(analysis.get("bpm") or 120)
    root = Element("Ableton", MajorVersion="5", MinorVersion="11.0_432", SchemaChangeCount="3")
    live = SubElement(root, "LiveSet")
    tempo = SubElement(live, "Tempo")
    manual = SubElement(tempo, "Manual", Value=str(bpm))
    _ = manual
    tracks = SubElement(live, "Tracks")
    for i, name in enumerate(["click", "guia", *stem_names]):
        t = SubElement(tracks, "AudioTrack", Id=str(i))
        SubElement(t, "Name").append(Element("EffectiveName", Value=name))
        SubElement(t, "DeviceChain")
    xml = tostring(root, encoding="utf-8", xml_declaration=True)
    with gzip.open(path, "wb") as f:
        f.write(xml)


def _readme_export(analysis: dict[str, Any], stems: list[str]) -> str:
    return f"""SecuenciaLive — paquete de secuencia
=====================================

BPM: {analysis.get("bpm")}
Tonalidad: {analysis.get("key")}
Compás: {analysis.get("time_signature")}
Conteo de entrada: {analysis.get("count_in_seconds", 0)} s
Transposición: {analysis.get("transpose_semitones", 0)} semitonos

Contenido
---------
- stems/: {", ".join(stems)}
- click.wav — metrónomo con conteo
- guia.wav — cues de sección (tonos)
- secuencia.json / marcadores.json / marcadores.cue
- ableton/SecuenciaLive_plantilla.als — plantilla con tempo (arrastra los WAV)

Ableton Live
------------
1. Abre SecuenciaLive_plantilla.als (o un set vacío a {analysis.get("bpm")} BPM).
2. Arrastra cada WAV a su pista; asegúrate de que empiecen en 1.1.1.
3. Usa click.wav en una pista de monitor o auriculares del baterista/MD.

Playback / Prime / MainStage
----------------------------
Importa los WAV alineados; el archivo secuencia.json tiene BPM y marcadores.

© SecuenciaLive — Jhon Fuentes. Los archivos de audio de origen no se almacenan
de forma permanente en el servidor (retención temporal según términos de uso).
"""
