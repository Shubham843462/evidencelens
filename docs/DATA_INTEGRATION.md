# Data integration — using real, audio-bearing video (incl. HoloAssist)

The app is **upload-first**: you drag a video into the UI and the backend
extracts frames and transcribes pre-cutoff speech itself. So "integrating data"
mainly means producing a short, authorized, web-playable clip and uploading it.

## Option A — your own footage (simplest, recommended to start)

Record a 30–60 s clip of a hands-on task with narration (phone is fine). You
own it, it has audio, and you can stage a visible mistake, a clean take, and an
ambiguous/occluded take. Drag it into the app and analyze.

## Option B — HoloAssist

HoloAssist is the project's reference dataset. It is gated and large, so you
obtain it yourself; this repo does not bundle it.

1. **Access.** Start at the official project page, <https://holoassist.github.io/>,
   and the annotation/release documentation. Follow their request/agreement
   process and download only the sessions you need. Each session folder contains
   several synchronized modalities (RGB video, audio, etc.).
2. **Pick an event.** Find a fine-grained *incorrect action* with an observable
   mistake, a sensible pre-mistake window, and a clear decision cutoff. Do not
   assume every incorrect action has one unambiguous cause or correction.
3. **Trim to the cutoff, keep audio.** Use the helper to export a short H.264+AAC
   clip that ends at your cutoff:

   ```bash
   python scripts/import_video_case.py \
     --input /path/to/session.mp4 \
     --output media/uploads_ready/holo_01.mp4 \
     --source-start 35 --source-cutoff 49 \
     --attribution "HoloAssist (Wang et al., ICCV 2023)"
   ```

4. **Upload it** in the app, add a task description, and click Analyze. The
   backend samples frames and transcribes the **pre-cutoff** speech; both go to
   the multimodal model.

### HoloAssist audio note (important)

HoloAssist's original recordings include an audio track, but some redistributions
(e.g. the `SitongGong/HoloAssist` Hugging Face mirror) ship **video-only** clips.
When the clip has no audio there is nothing for Whisper to transcribe. The
dataset still provides the speech as timestamped `Conversation` **Transcription**
annotations, so you can inject the official transcript instead:

```bash
python scripts/import_video_case.py \
  --input holoassist_raw/R105_DSLR.mp4 \
  --output media/uploads_ready/holo_dslr_lens.mp4 \
  --source-start 0 --source-cutoff 20 --mute \
  --annotations holoassist_raw/annotations.json --session R105-3Aug-DSLR \
  --attribution "HoloAssist (Wang et al., ICCV 2023)"
```

With `--annotations` + `--session`, the pre-cutoff `Conversation` transcriptions
are embedded in the clip's `comment` metadata. On upload the backend reads them
back and feeds them to the model exactly like a Whisper transcript — so you get
real footage **plus** real annotated speech, with post-cutoff correction excluded
by the same cutoff rule. Use `--mute` for mirror clips that have no audio track.

## The leakage rule (important with audio)

The instructor's correction *after* the mistake must never reach the initial
diagnosis — in audio form this is easy to leak. Two guards:

- **Export cutoff:** `import_video_case.py` ends the clip at the cutoff, so later
  correction audio is not in the file at all.
- **Runtime cutoff:** the app's "Analyze up to" control filters frames **and**
  transcript segments to `≤ cutoff` before anything reaches the model.

Keep the later correction as a **private evaluation reference** (your own notes),
not in any uploaded clip or prompt. Use it only for blinded scoring of whether
the AI's diagnosis/revision was actually right.

## Licensing and attribution

- Do not redistribute dataset video unless the license permits it. HoloAssist is
  for your authorized use; a local course demo you run yourself is fine.
- Record the source/credit (the script's `--attribution` is for your records).
- Avoid uploading other people's personal footage to an external model without
  permission. In live mode, frames and the pre-cutoff transcript are sent to the
  configured AI provider — note this to participants.

## Labeling for honest reporting

Mark every clip and every response as *synthetic*, *your own recording*,
*dataset-derived*, *scripted demo*, or *real model output*, as appropriate. A
valid evidence citation proves a frame exists; it is **not** semantic
verification. Score claim support manually (see `docs/EVALUATION.md`).
