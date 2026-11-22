"""Prepare an authorized video segment (e.g. a HoloAssist session) for upload.

The upload-first app does the frame extraction and speech transcription itself,
so this script's only job is to produce a short, web-playable, AUDIO-PRESERVING
clip that ends at your decision cutoff. You then drag that clip into the app at
http://localhost:5173 and analyze it like any other upload.

Why a cutoff at export time: the instructor's *post-mistake* correction speech
must not reach the initial diagnosis. Trimming the clip so it ends at the cutoff
removes that audio from everything the model can hear. Keep the later correction
separately as a private evaluation reference (never upload it for diagnosis).

Example (times are ORIGINAL recording seconds):
  python scripts/import_video_case.py \
    --input /path/to/holoassist_session.mp4 \
    --output media/uploads_ready/case_holo_01.mp4 \
    --source-start 35 --source-cutoff 49 \
    --attribution "HoloAssist (Wang et al., ICCV 2023)"

Requires FFmpeg. Verify you have the right to use the footage before sharing it.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def extract_pre_cutoff_transcript(annotations_path, session, start, cutoff):
    """Pull HoloAssist 'Conversation' transcriptions for a session, keep only
    speech before the cutoff, and return [{start,end,text}] with times made
    relative to the clip start. Post-cutoff (e.g. instructor correction) is
    dropped so it cannot leak into the diagnosis.
    """
    data = json.loads(Path(annotations_path).read_text())
    rec = next((r for r in data if r.get("video_name") == session), None)
    if rec is None:
        raise SystemExit(f"Session '{session}' not found in annotations.")
    segs = []
    for e in rec.get("events", []):
        if e.get("label") != "Conversation":
            continue
        s, en = float(e.get("start", 0.0)), float(e.get("end", 0.0))
        # keep speech that starts within the clip window and before the cutoff
        if s < start or s > cutoff + 1e-6:
            continue
        text = (e.get("attributes", {}).get("Transcription", "") or "").strip()
        if not text or text == "*unintelligible*":
            continue
        segs.append({"start": round(s - start, 3),
                     "end": round(max(en, s) - start, 3),
                     "text": text})
    segs.sort(key=lambda x: x["start"])
    return segs


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, help="Path to the source video")
    parser.add_argument("--output", default=None,
                        help="Output .mp4 path (default: media/uploads_ready/<input-stem>_clip.mp4)")
    parser.add_argument("--source-start", required=True, type=float,
                        help="Clip start in ORIGINAL recording seconds")
    parser.add_argument("--source-cutoff", required=True, type=float,
                        help="Decision cutoff in ORIGINAL recording seconds (clip ends here)")
    parser.add_argument("--attribution", default="",
                        help="Source/credit, kept for your own records")
    parser.add_argument("--mute", action="store_true",
                        help="Drop the audio track (use for mirrors whose clips have no audio)")
    parser.add_argument("--annotations", default=None,
                        help="HoloAssist annotation JSON. If given with --session, the "
                             "pre-cutoff spoken transcript is embedded in the clip metadata.")
    parser.add_argument("--session", default=None,
                        help="Session video_name to pull the transcript for (e.g. R105-3Aug-DSLR)")
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        parser.error("ffmpeg not found. Install FFmpeg (e.g. `brew install ffmpeg`).")

    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        parser.error("Video input does not exist")

    duration = args.source_cutoff - args.source_start
    if duration <= 0:
        parser.error("--source-cutoff must be greater than --source-start")

    out = Path(args.output).expanduser() if args.output else \
        ROOT / "media" / "uploads_ready" / f"{src.stem}_clip.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)

    # Optional: pull the official pre-cutoff transcript and embed it in the MP4
    # as a metadata comment, so it travels with the file through a browser upload.
    transcript = []
    if args.annotations and args.session:
        transcript = extract_pre_cutoff_transcript(
            args.annotations, args.session, args.source_start, args.source_cutoff)

    # Re-encode to H.264 (+ AAC) so the browser can play it.
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", str(args.source_start), "-i", str(src),
           "-t", str(duration),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-movflags", "+faststart"]
    if args.mute:
        cmd += ["-an"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    if transcript:
        # MP4 only reliably preserves a small set of standard metadata keys, so
        # we stash the JSON transcript in the standard 'comment' tag (prefixed so
        # the backend recognizes it). The backend reads it back with ffprobe.
        payload = "EVLENS_TRANSCRIPT:" + json.dumps(transcript, ensure_ascii=True)
        cmd += ["-metadata", "comment=" + payload]
    cmd += [str(out)]
    subprocess.run(cmd, check=True)

    print(f"Wrote pre-cutoff clip: {out}")
    print(f"  Length: {duration:.2f} s  (original {args.source_start}s -> {args.source_cutoff}s)")
    print(f"  Audio:  {'muted' if args.mute else 'preserved (the app will transcribe pre-cutoff speech)'}")
    if transcript:
        print(f"  Transcript: embedded {len(transcript)} pre-cutoff segment(s) from annotations")
    if args.attribution:
        print(f"  Source: {args.attribution}")
    print("\nNext steps:")
    print("  1. Open the app (http://localhost:5173) and drag this clip into the upload area.")
    print("  2. Add a task description; click Analyze. Frames + pre-cutoff speech go to the model.")
    print("  3. Keep any later instructor correction OUT of the app; store it as a private")
    print("     evaluation reference only.")


if __name__ == "__main__":
    main()
