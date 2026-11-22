# EvidenceLens — upload-first human–AI error-recovery prototype

A web app where anyone **uploads a physical-task video**, gets an AI diagnosis
grounded in frames extracted from that video, clicks timestamped evidence to
check it, and **challenges** a claim so the AI can revise, uphold, or abstain.

This implements the *EvidenceLens Upload-First Implementation Guide (v2)*. It
replaces the earlier case-picker-first starter: the first screen is now a video
upload area, not a library of preloaded cases.

The project investigates two research questions:

- **RQ1 — Evidence exploration.** How do timestamped video links help a human
  check an AI-generated mistake diagnosis?
- **RQ2 — Collaborative correction.** How can a claim-specific objection plus a
  selected frame help an AI revise, uphold, or withdraw a diagnosis?

This is a **course prototype**, not a completed study. No model accuracy, user
trust, or HoloAssist result is claimed.

## 1. What works

- Upload-first React + Vite page: drag/drop or browse (MP4/WebM), local preview,
  optional task context, Analyze, clickable evidence timeline, claim challenge
  with an attached frame, and a before/after revision panel.
- FastAPI backend with four MVP endpoints: `POST /api/videos`,
  `POST /api/analyze`, `POST /api/challenge`, `GET /api/videos/{id}`, plus
  `GET /api/frames/{video_id}/{eid}` and `GET /health`.
- Real video pipeline: `ffprobe` validation, UUID-safe storage, `ffmpeg` frame
  sampling into evidence IDs (`E01`, `E02`, …) with accurate timestamps.
- **Multimodal:** pre-cutoff speech is extracted with `ffmpeg` and transcribed
  with Whisper, then added to the prompt as unverified prior context — so the
  diagnosis is grounded in **frames + speech**, shown on the same timeline.
- An **"Analyze up to" cutoff** that hides later frames **and** later speech from
  the model (leakage guard for instructor corrections).
- Response validation that rejects unknown or post-cutoff evidence IDs and
  blocks corrections on non-error / abstaining results.
- Two model backends: an **offline demo** stand-in (deterministic, built from the
  real extracted frames, for UI testing) and an optional **live** multimodal
  model that receives the actual pre-cutoff frames and transcript.

## 2. Prerequisites

- **Python 3.10+**, **Node 18+**, npm.
- **FFmpeg** (provides `ffmpeg` and `ffprobe`) — required for upload processing.
  - macOS: `brew install ffmpeg`
  - Debian/Ubuntu: `sudo apt install ffmpeg`
  - Windows: download from https://ffmpeg.org/download.html and add to PATH.

## 3. Run the app

**Terminal A — backend** (from the project root):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
uvicorn app.main:app --app-dir backend --reload --port 8000
```

Windows PowerShell: activate with `.venv\Scripts\Activate.ps1` and use
`copy .env.example .env`.

**Terminal B — frontend:**

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**; backend docs are at **http://localhost:8000/docs**.

Journey: drag in a short MP4/WebM → *Upload & preview* → *Analyze video* → click
an evidence timestamp to seek → seek the player and *Attach current frame* →
pick the disputed claim, type an objection → *Submit challenge & re-analyze* →
read the REVISE / UPHOLD / ABSTAIN reassessment.

## 4. Demo vs live model

Default is `demo`: deterministic, offline, no API key. Its wording is scripted
(though the cited frames and timestamps are real for your upload), so it is for
**interface testing only** and is not evidence of model capability.

For real analysis, edit the project-root `.env`:

```dotenv
EVIDENCELENS_MODE=live
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4.1-mini
```

Restart the backend. In live mode the sampled JPEG frames, the **pre-cutoff
spoken transcript** (Whisper), and your task text are sent to the configured
provider. **API charges may apply** (the model call plus transcription). A valid
evidence link proves a frame exists; it does **not** prove the frame supports the
claim — verify visually. Speech is treated as unverified prior context, not
ground truth. Disable transcription with `EVIDENCELENS_TRANSCRIBE=0`.

For dataset clips that ship **without audio** (e.g. the HoloAssist HF mirror),
the import script can embed the dataset's own timestamped transcript annotations
into the clip, and the backend uses those instead of Whisper. See
`docs/DATA_INTEGRATION.md`.

### Multimodality and the cutoff

Upload a clip **with audio** (e.g. a narrated task). After upload the UI shows how
many speech segments were found and a **"Analyze up to"** slider. Frames and
transcript segments after that cutoff are withheld from the model, so a later
instructor correction can't leak into the initial diagnosis. The transcript panel
lists the pre-cutoff speech the model was given; click a line to seek the video.

## 5. API contract

| Endpoint | Request | Response |
|---|---|---|
| `POST /api/videos` | multipart `file` (+ optional `task`) | `video_id`, `preview_url`, `duration_s`, `format`, `frame_count` |
| `POST /api/analyze` | `video_id`, `task_description`, `expected_steps`, `cutoff_s?` | diagnosis: `status`, `claims[]`, `correction`, `evidence[]`, `uncertainty` |
| `POST /api/challenge` | `diagnosis_id`, `claim_id`, `selected_time_s`, `user_objection` | `outcome` (revise/uphold/abstain), changed claims, rationale, evidence |
| `GET /api/videos/{id}` | path `video_id` | streams the stored MP4/WebM |
| `GET /api/frames/{video_id}/{eid}` | path | serves one extracted evidence frame |

`status` may be `possible_error`, `no_error_observed`, or
`insufficient_evidence`. In the last two the UI does not force a correction.

## 6. Code map

```text
backend/app/main.py        # FastAPI: upload/analyze/challenge + cutoff + validation
backend/app/video.py       # ffprobe validation, UUID storage, ffmpeg frame sampling
backend/app/audio.py       # audio extraction + pre-cutoff Whisper transcription
backend/app/live_model.py  # real multimodal adapter (frames + speech -> grounded JSON)
backend/app/demo_model.py  # offline deterministic stand-in for UI testing
backend/app/schemas.py     # Pydantic request/response contracts
backend/tests/test_api.py  # endpoint tests (demo mode)
backend/uploads/<id>/      # per-upload video + extracted frames (gitignored)
frontend/src/App.jsx       # upload-first single-page UI + state machine
frontend/src/api.js        # fetch helpers incl. multipart upload
frontend/src/styles.css    # responsive styling
```

## 7. Storage, privacy, limits

- Uploads are stored under random UUID directories, never the client filename.
- MP4/WebM only; defaults are ≤100 MB and ≤2 minutes (configurable in `.env`).
- Interaction logs (`backend/results/`) record IDs, outcome, and timestamp only —
  no raw video and no objection text.
- CORS is restricted to the frontend origin.
- On model failure the app shows a retry message and keeps the uploaded video;
  it never fabricates an answer.

## 8. Not included (by design)

No dataset downloader, webcam/AR pipeline, video embeddings, model fine-tuning,
or multi-agent framework. The old synthetic cases and `data/` remain only as an
optional, clearly labeled sample — never the required main flow.

## 9. Research integrity

Use this as an implementation starting point and write the course report in your
own words from what you actually built and measured. Disclose AI-assisted coding.
A valid citation is not semantic verification; use a manual claim-support rubric
for evaluation. See `docs/EVALUATION.md` and `docs/DATA_INTEGRATION.md`.
