"""Upload handling and frame extraction for user-provided videos.

Pipeline (guide section 06):
  A. validate   -> inspect real media with ffprobe, enforce size/duration limits
  B. save safely -> random UUID directory, never trust the client filename
  C. preview    -> stream the stored file back for HTML5 playback
  D. cutoff     -> default to end of video; caller may pass an earlier cutoff
  E. sample     -> extract ~12-20 JPEG frames across the allowed range (ffmpeg)
  F. evidence   -> label frames E01/E02/... with accurate seconds

Nothing here trusts the uploaded filename for a disk path.
"""
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from . import audio

ROOT = Path(__file__).resolve().parents[2]
UPLOADS = ROOT / "backend" / "uploads"

# Configurable limits (guide section 09). Override via environment.
MAX_BYTES = int(os.getenv("EVIDENCELENS_MAX_BYTES", str(100 * 1024 * 1024)))  # 100 MB
MAX_DURATION_S = float(os.getenv("EVIDENCELENS_MAX_DURATION_S", "120"))        # 2 minutes
TARGET_FRAMES = int(os.getenv("EVIDENCELENS_TARGET_FRAMES", "16"))            # 12-20
FRAME_WIDTH = int(os.getenv("EVIDENCELENS_FRAME_WIDTH", "640"))

ALLOWED = {
    "video/mp4": "mp4",
    "video/webm": "webm",
}


class UploadError(ValueError):
    """Raised for user-fixable upload problems (bad type, too big, corrupt)."""


def _which(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise UploadError(
            f"'{binary}' is required for video processing but was not found. "
            "Install FFmpeg (e.g. `brew install ffmpeg`) and restart the backend."
        )
    return path


def _ffprobe_duration(path: Path) -> float:
    ffprobe = _which("ffprobe")
    out = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise UploadError("The file could not be read as a valid video.")
    try:
        data = json.loads(out.stdout)
        duration = float(data["format"]["duration"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        raise UploadError("The file could not be read as a valid video.") from exc
    if duration <= 0:
        raise UploadError("The video has no measurable duration.")
    return duration


def save_upload(raw: bytes, content_type: str) -> dict:
    """Validate and persist an uploaded video under a random UUID directory."""
    ext = ALLOWED.get((content_type or "").split(";")[0].strip().lower())
    if not ext:
        raise UploadError("Unsupported file type. Upload an MP4 or WebM video.")
    if not raw:
        raise UploadError("The uploaded file is empty.")
    if len(raw) > MAX_BYTES:
        raise UploadError(
            f"File is too large. The limit is {MAX_BYTES // (1024 * 1024)} MB."
        )

    video_id = "v_" + uuid.uuid4().hex[:10]
    folder = UPLOADS / video_id
    folder.mkdir(parents=True, exist_ok=True)
    video_path = folder / f"video.{ext}"
    video_path.write_bytes(raw)

    try:
        duration = _ffprobe_duration(video_path)
    except UploadError:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    if duration > MAX_DURATION_S:
        shutil.rmtree(folder, ignore_errors=True)
        raise UploadError(
            f"Video is too long. The limit is {int(MAX_DURATION_S)} seconds."
        )

    frames = extract_frames(folder, video_path, duration, cutoff_s=duration)
    # Transcribe speech once at upload time (best-effort; empty if no audio/key).
    transcript = audio.transcribe(folder, video_path)
    meta = {
        "video_id": video_id,
        "ext": ext,
        "format": content_type.split(";")[0].strip().lower(),
        "duration_s": round(duration, 3),
        "cutoff_s": round(duration, 3),
        "video_path": str(video_path),
        "frames": frames,
        "has_audio": bool(transcript),
        "transcript": transcript,
    }
    (folder / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def extract_frames(folder: Path, video_path: Path, duration: float,
                   cutoff_s: float) -> list[dict]:
    """Sample evenly spaced JPEG frames from 0..cutoff and label them E01..En."""
    ffmpeg = _which("ffmpeg")
    cutoff = max(0.1, min(cutoff_s, duration))
    frames_dir = folder / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    n = max(2, min(TARGET_FRAMES, 20))
    # Evenly spaced sample times strictly inside the allowed window.
    step = cutoff / (n + 1)
    times = [round(step * (i + 1), 3) for i in range(n)]

    frames = []
    for i, t in enumerate(times, 1):
        eid = f"E{i:02d}"
        out_path = frames_dir / f"{eid}.jpg"
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", str(t), "-i", str(video_path),
            "-frames:v", "1",
            "-vf", f"scale={FRAME_WIDTH}:-2",
            "-q:v", "4", str(out_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not out_path.is_file():
            # Skip a frame that could not be read rather than failing the upload.
            continue
        frames.append({"id": eid, "time_s": t,
                       "frame_url": f"/api/frames/{folder.name}/{eid}"})

    if len(frames) < 2:
        raise UploadError("Could not extract usable frames from this video.")
    return frames


def load_meta(video_id: str) -> dict | None:
    meta_path = UPLOADS / video_id / "meta.json"
    if not meta_path.is_file():
        return None
    return json.loads(meta_path.read_text())


def frame_path(video_id: str, evidence_id: str) -> Path | None:
    # evidence_id is validated against stored metadata by the caller.
    p = UPLOADS / video_id / "frames" / f"{evidence_id}.jpg"
    return p if p.is_file() else None


def video_file(video_id: str) -> Path | None:
    meta = load_meta(video_id)
    if not meta:
        return None
    p = Path(meta["video_path"])
    return p if p.is_file() else None


def cleanup_older_than(seconds: float) -> int:
    """Remove upload directories older than a cutoff. Returns count removed."""
    import time
    if not UPLOADS.exists():
        return 0
    removed = 0
    now = time.time()
    for child in UPLOADS.iterdir():
        if child.is_dir() and now - child.stat().st_mtime > seconds:
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
    return removed
