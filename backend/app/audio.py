"""Audio extraction and pre-cutoff speech transcription.

Multimodality: the diagnosis is grounded in vision (sampled frames) AND
language-from-speech (a timestamped transcript). To respect the guide's
leakage rule, only speech at or before the decision cutoff is ever exposed to
the model. Post-cutoff instructor corrections stay out of the prompt.

Transcription uses the OpenAI Whisper API (model configurable). In demo mode,
or when transcription is disabled / no API key is present, this degrades
gracefully to an empty transcript so the app still runs offline.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path


def _has(binary: str) -> bool:
    return bool(shutil.which(binary))


def embedded_transcript(video_path: Path) -> list[dict]:
    """Read a transcript embedded in the MP4 metadata by import_video_case.py.

    Returns [{start,end,text}] or []. This lets real dataset clips that have no
    audio track (e.g. the HoloAssist HF mirror) still carry their official
    pre-cutoff annotated transcript.
    """
    if not _has("ffprobe"):
        return []
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags",
         "-of", "json", str(video_path)],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        return []
    try:
        tags = (json.loads(out.stdout).get("format", {}).get("tags", {}) or {})
    except json.JSONDecodeError:
        return []
    # The transcript is stashed in the standard 'comment' tag (MP4 preserves it),
    # prefixed with a marker. Also accept a bare custom key if present.
    raw = (tags.get("evidencelens_transcript")
           or tags.get("EVIDENCELENS_TRANSCRIPT")
           or tags.get("comment") or tags.get("COMMENT"))
    if not raw:
        return []
    marker = "EVLENS_TRANSCRIPT:"
    if raw.startswith(marker):
        raw = raw[len(marker):]
    try:
        segs = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    clean = []
    for s in segs if isinstance(segs, list) else []:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        clean.append({"start": round(float(s.get("start", 0.0)), 3),
                      "end": round(float(s.get("end", 0.0)), 3), "text": text})
    return clean


def extract_audio(folder: Path, video_path: Path) -> Path | None:
    """Extract a 16 kHz mono WAV. Returns None if the video has no audio track."""
    if not _has("ffmpeg") or not _has("ffprobe"):
        return None
    # Does the file even have an audio stream?
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(video_path)],
        capture_output=True, text=True,
    )
    if probe.returncode != 0 or not probe.stdout.strip():
        return None
    out = folder / "audio.wav"
    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(out)],
        capture_output=True, text=True,
    )
    if res.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        return None
    return out


def transcribe(folder: Path, video_path: Path) -> list[dict]:
    """Get timestamped speech segments for a clip.

    Order of preference:
      1. A transcript embedded in the MP4 metadata (e.g. HoloAssist annotations
         added by import_video_case.py) — used in ANY mode, no API needed.
      2. Whisper transcription of the audio track (live mode only).
    Returns [] when neither is available. Callers filter by cutoff.
    """
    embedded = embedded_transcript(video_path)
    if embedded:
        return embedded

    mode = os.getenv("EVIDENCELENS_MODE", "demo").lower()
    enabled = os.getenv("EVIDENCELENS_TRANSCRIBE", "1") != "0"
    if not enabled or mode != "live" or not os.getenv("OPENAI_API_KEY"):
        return []

    audio = extract_audio(folder, video_path)
    if not audio:
        return []

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        model = os.getenv("EVIDENCELENS_WHISPER_MODEL", "whisper-1")
        with audio.open("rb") as fh:
            result = client.audio.transcriptions.create(
                model=model, file=fh,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        data = result.model_dump() if hasattr(result, "model_dump") else result
        segments = []
        for seg in data.get("segments", []) or []:
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            segments.append({
                "start": round(float(seg.get("start", 0.0)), 3),
                "end": round(float(seg.get("end", 0.0)), 3),
                "text": text,
            })
        # Fallback: no per-segment timing but a flat transcript came back.
        if not segments and (data.get("text") or "").strip():
            segments = [{"start": 0.0, "end": 0.0, "text": data["text"].strip()}]
        return segments
    except Exception:
        # Transcription is best-effort; never fail the upload because of it.
        return []


def segments_before(segments: list[dict], cutoff_s: float) -> list[dict]:
    """Keep only speech that starts at or before the cutoff (leakage guard)."""
    return [s for s in segments if s.get("start", 0.0) <= cutoff_s + 1e-6]


def transcript_text(segments: list[dict]) -> str:
    """Render allowed segments as a compact timestamped block for a prompt."""
    lines = []
    for s in segments:
        stamp = f"{int(s['start'] // 60):02d}:{int(s['start'] % 60):02d}"
        lines.append(f"[{stamp}] {s['text']}")
    return "\n".join(lines)
