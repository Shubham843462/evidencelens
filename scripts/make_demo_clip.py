"""Generate short narrated demo clips to exercise the multimodal pipeline.

Each clip pairs animated frames with spoken narration (H.264 + AAC) so you can
test frames + speech without filming. Three scenes map to the three challenge
outcomes you want to demonstrate (RQ2):

  uphold  -> clear mistake; a wrong/agreeing objection should be resisted
  revise  -> the narration states the WRONG cause while the frames support a
             different reading, so an evidence-backed objection can correct it
  abstain -> the key moment is occluded, so neither side can be confirmed

Usage:
  python scripts/make_demo_clip.py            # builds all three
  python scripts/make_demo_clip.py uphold     # builds just one

macOS only for narration (uses `say`). Requires ffmpeg + Pillow.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "media" / "uploads_ready"
W, H, FPS = 854, 480, 10
TAIL_S = 1.0


def audio_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def font(size):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc"):
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _base(title):
    im = Image.new("RGB", (W, H), (22, 36, 42))
    d = ImageDraw.Draw(im)
    d.text((40, 28), title, font=font(40), fill=(230, 245, 242))
    return im, d


# ---- Scene 1: UPHOLD -------------------------------------------------------
# Clear mistake (screw in A, target is B). Narration matches the frames.
UPHOLD_NARR = (
    "I am assembling the shelf bracket. The guide says the arrow should point to "
    "the right. First I align the bracket. Now I insert the screw into hole A. "
    "Wait, the guide marked hole B as the target, so this may be the wrong hole."
)


def draw_uphold(d, t, dur):
    f, f_sm = font(26), font(20)
    d.rectangle([120, 150, 320, 230], outline=(90, 200, 170), width=4)
    d.line([150, 190, 290, 190], fill=(120, 230, 195), width=6)
    d.polygon([(290, 172), (320, 190), (290, 208)], fill=(120, 230, 195))
    d.text((120, 240), "Bracket arrow -> RIGHT (ok)", font=f_sm, fill=(150, 220, 205))
    ax, bx, hy = 520, 680, 300
    d.ellipse([ax - 26, hy - 26, ax + 26, hy + 26], outline=(220, 220, 220), width=4)
    d.ellipse([bx - 26, hy - 26, bx + 26, hy + 26], outline=(220, 220, 220), width=4)
    d.text((ax - 10, hy + 34), "A", font=f, fill=(240, 240, 240))
    d.text((bx - 10, hy + 34), "B", font=f, fill=(240, 240, 240))
    d.text((bx - 70, hy - 80), "TARGET: B", font=f_sm, fill=(250, 205, 110))
    end = dur * 0.8
    sy = int(120 + min(1.0, t / end) * (hy - 120 - 30))
    d.rectangle([ax - 6, sy - 40, ax + 6, sy], fill=(200, 200, 210))
    d.polygon([(ax - 6, sy), (ax + 6, sy), (ax, sy + 14)], fill=(200, 200, 210))
    if t >= end:
        d.text((ax - 130, hy + 70), "screw inserted into A", font=f_sm, fill=(240, 140, 120))


# ---- Scene 2: REVISE -------------------------------------------------------
# Narration blames the WRONG thing ("the cable is in the wrong port") but the
# frames show the cable going into the correct green port; the actual visible
# problem is that the connector is upside-down. A supported objection pointing
# at orientation (not port choice) should make the model revise.
REVISE_NARR = (
    "I am tightening the bolts on this panel. The top bolt looks a little loose to "
    "me, so I think the top one still needs tightening. Let me look over the panel "
    "before I finish up."
)


def draw_revise(d, t, dur):
    # Deliberately ambiguous: three bolts, each marked with a small check or cross.
    # The TOP bolt shows a check (tight); the BOTTOM bolt shows a cross (loose) but
    # it is small and easy to miss. The narration nudges attention to the TOP bolt.
    # So the first diagnosis tends to echo "top bolt" / "no clear issue up top".
    # A challenge pointing at the visible cross on the BOTTOM bolt can then revise.
    f, f_sm = font(24), font(18)
    cx = 430
    bolts = [("TOP", 150, True), ("MIDDLE", 250, True), ("BOTTOM", 350, False)]
    for name, by, tight in bolts:
        d.ellipse([cx - 24, by - 24, cx + 24, by + 24], outline=(200, 205, 210), width=4)
        d.line([cx - 14, by, cx + 14, by], fill=(200, 205, 210), width=5)
        d.text((cx + 50, by - 10), name, font=f_sm, fill=(190, 200, 205))
        mark_x = cx - 120
        if tight:
            d.line([mark_x, by, mark_x + 10, by + 10], fill=(110, 210, 150), width=4)
            d.line([mark_x + 10, by + 10, mark_x + 26, by - 12], fill=(110, 210, 150), width=4)
        else:
            d.line([mark_x, by - 10, mark_x + 22, by + 12], fill=(230, 120, 110), width=4)
            d.line([mark_x, by + 12, mark_x + 22, by - 10], fill=(230, 120, 110), width=4)
    d.text((120, 120), "Panel bolts: check = tight, cross = loose", font=f_sm, fill=(170, 195, 200))


# ---- Scene 3: ABSTAIN ------------------------------------------------------
# The key contact point is hidden behind a hand/obstruction the whole time, so
# the state genuinely cannot be determined from the frames.
ABSTAIN_NARR = (
    "I am checking the connection underneath. My hand is covering the contact "
    "point, so the camera cannot really see whether it is seated. I am not sure "
    "if this is correct from this angle."
)


def draw_abstain(d, t, dur):
    f_sm = font(20)
    cx, cy = 430, 280
    d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], outline=(120, 140, 150), width=3)
    d.text((cx - 70, cy + 44), "contact point (hidden)", font=f_sm, fill=(150, 160, 170))
    # A big occluding blob (a "hand") covers the contact point throughout.
    ox = cx - 10 + int(20 * (0.5 - abs((t / dur) - 0.5)))  # drifts slightly, never clears
    d.ellipse([ox - 95, cy - 70, ox + 95, cy + 110], fill=(70, 60, 55))
    d.text((120, 150), "View of the contact point is obstructed", font=f_sm, fill=(210, 170, 120))


SCENES = {
    "uphold":  ("Shelf bracket assembly",   UPHOLD_NARR,  draw_uphold,  "demo_uphold_bracket.mp4"),
    "revise":  ("Module cable connection",  REVISE_NARR,  draw_revise,  "demo_revise_cable.mp4"),
    "abstain": ("Underside connection check", ABSTAIN_NARR, draw_abstain, "demo_abstain_occluded.mp4"),
}


def build(scene_key):
    title, narration, draw_fn, out_name = SCENES[scene_key]
    out = OUT_DIR / out_name
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        speech = tmp / "speech.aiff"
        subprocess.run(["say", "-o", str(speech), narration], check=True)
        dur = audio_duration(speech) + TAIL_S
        total = int(round(dur * FPS))

        frames = tmp / "frames"
        frames.mkdir()
        for n in range(total):
            im, d = _base(title)
            draw_fn(d, n / FPS, dur)
            im.save(frames / f"f{n:04d}.png")

        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-framerate", str(FPS), "-i", str(frames / "f%04d.png"),
            "-i", str(speech),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high",
            "-movflags", "+faststart", "-c:a", "aac", "-b:a", "128k",
            str(out),
        ], check=True)
    print(f"built {out}  ({dur:.1f}s)")


def main():
    keys = sys.argv[1:] or list(SCENES)
    for k in keys:
        if k not in SCENES:
            print(f"unknown scene '{k}'; choose from {list(SCENES)}")
            continue
        build(k)


if __name__ == "__main__":
    main()
