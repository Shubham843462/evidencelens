"""EvidenceLens upload-first API.

The user uploads their own video; the backend extracts timestamped frames and
sends those frames (not a filename) to a multimodal model. Evidence IDs are
generated from the uploaded video and are the only IDs the model may cite.

Endpoints (guide section 05):
  POST /api/videos        multipart upload -> video_id, preview_url, duration, frames
  POST /api/analyze       JSON -> structured diagnosis grounded in extracted frames
  POST /api/challenge     JSON -> independent revise/uphold/abstain re-analysis
  GET  /api/videos/{id}   stream the stored video for HTML5 playback
  GET  /api/frames/{id}/{eid}  serve one extracted evidence frame
  GET  /health            mode + limits
"""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import ValidationError

from . import audio, demo_model, live_model, video
from .schemas import (AnalyzeRequest, ChallengeRequest, ChallengeResult,
                      Diagnosis, EvidenceFrame, VideoUploadResponse)
from .video import UploadError

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

MODE = os.getenv("EVIDENCELENS_MODE", "demo").lower()
if MODE not in ("demo", "live"):
    raise RuntimeError("EVIDENCELENS_MODE must be demo or live")

FRONTEND_ORIGINS = os.getenv(
    "EVIDENCELENS_CORS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

app = FastAPI(title="EvidenceLens", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in FRONTEND_ORIGINS if o.strip()],
    allow_credentials=False, allow_methods=["*"], allow_headers=["*"],
)

# In-memory diagnosis store (prototype scope, not durable).
DIAGNOSES: dict[str, dict] = {}


def _validate_evidence(meta, ids):
    """Every cited ID must belong to this upload and sit at/before the cutoff."""
    allowed = {f["id"] for f in meta["frames"] if f["time_s"] <= meta["cutoff_s"] + 1e-6}
    unknown = set(ids) - allowed
    if unknown:
        raise HTTPException(422, f"Unknown or post-cutoff evidence ID: {sorted(unknown)}")


def _validate_diagnosis(meta, diag: Diagnosis):
    for claim in diag.claims:
        _validate_evidence(meta, claim.evidence_ids)
    if diag.status == "possible_error" and not diag.claims:
        raise HTTPException(502, "Model flagged an error but cited no claim.")
    if diag.status != "possible_error" and diag.correction.strip():
        raise HTTPException(502, "Model returned a correction without a supported error.")


def _apply_cutoff(meta, cutoff_s):
    """Return a view of meta with frames AND transcript limited to <= cutoff.

    This is the leakage guard: post-cutoff frames and speech are removed before
    anything reaches a model.
    """
    cut = min(cutoff_s, meta["cutoff_s"]) if cutoff_s is not None else meta["cutoff_s"]
    frames = [f for f in meta["frames"] if f["time_s"] <= cut + 1e-6]
    transcript = audio.segments_before(meta.get("transcript") or [], cut)
    return {**meta, "cutoff_s": cut, "frames": frames, "transcript": transcript}


def _attach_evidence(meta, diag: Diagnosis) -> Diagnosis:
    """Fill diag.evidence from the stored frames for every cited ID."""
    cited = {eid for c in diag.claims for eid in c.evidence_ids}
    by_id = {f["id"]: f for f in meta["frames"]}
    diag.evidence = [
        EvidenceFrame(id=eid, time_s=by_id[eid]["time_s"], frame_url=by_id[eid]["frame_url"])
        for eid in sorted(cited) if eid in by_id
    ]
    return diag


@app.get("/health")
def health():
    return {"ok": True, "mode": MODE,
            "max_mb": video.MAX_BYTES // (1024 * 1024),
            "max_duration_s": video.MAX_DURATION_S,
            "model_note": "In live mode, sampled frames, pre-cutoff speech (transcribed), and task text are sent to the configured AI provider."}


@app.post("/api/videos", response_model=VideoUploadResponse)
async def upload_video(file: UploadFile = File(...), task: str = Form(default="")):
    try:
        raw = await file.read()
        meta = video.save_upload(raw, file.content_type or "")
    except UploadError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # ffmpeg/ffprobe missing or unexpected failure
        raise HTTPException(500, "Video processing failed: " + str(exc)) from exc
    return VideoUploadResponse(
        video_id=meta["video_id"],
        preview_url=f"/api/videos/{meta['video_id']}",
        duration_s=meta["duration_s"],
        format=meta["format"],
        frame_count=len(meta["frames"]),
        has_audio=meta.get("has_audio", False),
        transcript=meta.get("transcript", []),
    )


@app.get("/api/videos/{video_id}")
def stream_video(video_id: str):
    path = video.video_file(video_id)
    if not path:
        raise HTTPException(404, "Video not found")
    media_type = "video/webm" if path.suffix == ".webm" else "video/mp4"
    return FileResponse(path, media_type=media_type)


@app.get("/api/frames/{video_id}/{evidence_id}")
def get_frame(video_id: str, evidence_id: str):
    meta = video.load_meta(video_id)
    if not meta or evidence_id not in {f["id"] for f in meta["frames"]}:
        raise HTTPException(404, "Frame not found")
    path = video.frame_path(video_id, evidence_id)
    if not path:
        raise HTTPException(404, "Frame not found")
    return FileResponse(path, media_type="image/jpeg")


@app.post("/api/analyze", response_model=Diagnosis)
def analyze(payload: AnalyzeRequest):
    meta = video.load_meta(payload.video_id)
    if not meta:
        raise HTTPException(404, "Unknown video_id; upload again")

    # Apply the (optional) earlier cutoff to frames and speech alike.
    meta = _apply_cutoff(meta, payload.cutoff_s)
    if len(meta["frames"]) < 2:
        raise HTTPException(422, "Cutoff leaves too few frames to analyze")

    if MODE == "live" and not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(503, "Live mode needs OPENAI_API_KEY in .env")

    try:
        raw = (demo_model.analyze(meta, payload.task_description, payload.expected_steps)
               if MODE == "demo"
               else live_model.analyze(meta, payload.task_description, payload.expected_steps))
        diag = Diagnosis.model_validate({**raw, "diagnosis_id": "d_" + uuid.uuid4().hex[:10],
                                         "video_id": meta["video_id"], "mode": MODE,
                                         "used_transcript": meta["transcript"]})
        _validate_diagnosis(meta, diag)
        diag = _attach_evidence(meta, diag)
    except (ValidationError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(502, "Invalid model output: " + str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, "Analysis unavailable — retry. (check server logs/credentials)") from exc

    DIAGNOSES[diag.diagnosis_id] = {"diagnosis": diag, "cutoff_s": meta["cutoff_s"]}
    return diag


@app.post("/api/challenge", response_model=ChallengeResult)
def challenge(payload: ChallengeRequest):
    stored = DIAGNOSES.get(payload.diagnosis_id)
    if not stored:
        raise HTTPException(404, "Diagnosis not found; run Analyze again")
    original: Diagnosis = stored["diagnosis"]
    meta = video.load_meta(original.video_id)
    if not meta:
        raise HTTPException(404, "Video for this diagnosis is gone; upload again")
    # Same cutoff the original diagnosis used — frames and speech both limited.
    meta = _apply_cutoff(meta, stored["cutoff_s"])

    if payload.claim_id not in {c.id for c in original.claims}:
        raise HTTPException(422, "Unknown claim ID")
    if payload.selected_time_s > meta["cutoff_s"] + 1e-6:
        raise HTTPException(422, "Selected time is after the analysis cutoff")

    if MODE == "live" and not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(503, "Live mode needs OPENAI_API_KEY in .env")

    try:
        raw = (demo_model.challenge(meta, original, payload.claim_id, payload.selected_time_s, payload.user_objection)
               if MODE == "demo"
               else live_model.challenge(meta, original, payload.claim_id, payload.selected_time_s, payload.user_objection))
        result = ChallengeResult.model_validate({**raw, "video_id": meta["video_id"],
                                                 "diagnosis_id": original.diagnosis_id, "mode": MODE})
        _validate_evidence(meta, result.evidence_ids)
        valid_claims = {c.id for c in original.claims}
        if not set(result.changed_claims).issubset(valid_claims):
            raise HTTPException(502, "Model changed an unknown claim ID")
        if result.outcome == "abstain" and result.correction.strip():
            raise HTTPException(502, "Abstaining result returned an actionable correction")
    except (ValidationError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(502, "Invalid model output: " + str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, "Re-analysis unavailable — retry. (check server logs/credentials)") from exc

    _log_interaction(meta["video_id"], original.diagnosis_id, result.outcome)
    return result


def _log_interaction(video_id, diagnosis_id, outcome):
    # De-identified: IDs, outcome and timestamp only. No raw video or objection text.
    import json
    logs = ROOT / "backend" / "results"
    logs.mkdir(parents=True, exist_ok=True)
    with (logs / "interaction_logs.jsonl").open("a") as f:
        f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(),
                            "video_id": video_id, "diagnosis_id": diagnosis_id,
                            "outcome": outcome, "mode": MODE}) + "\n")
