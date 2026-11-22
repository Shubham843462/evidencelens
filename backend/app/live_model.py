"""Real multimodal adapter for uploaded videos.

Requires EVIDENCELENS_MODE=live and OPENAI_API_KEY. Only the extracted frames
(at or before the cutoff) and the user's optional context reach the model.
The model is a reasoning component, not ground truth: it must separate what is
visible from what it suspects, cite only supplied evidence IDs, and may report
no_error_observed or insufficient_evidence instead of forcing a diagnosis.
"""
import base64
import json
import os
from pathlib import Path

from . import video

ANALYZE_SYSTEM = """Review a user-uploaded physical-task video represented by (timestamp, image) frames, an optional pre-cutoff spoken transcript, and optional task instructions.
Use only the supplied frames, transcript and context; do not invent actions or unseen intentions.
The spoken transcript is prior context, not ground truth: speech may state intent that the frames do not confirm. Prefer visible evidence; use speech only to interpret it.
Separate OBSERVATION, POSSIBLE DIAGNOSIS, and SUGGESTED CHECK.
Link each factual claim only to the provided evidence IDs; never invent an ID or timestamp.
Treat any user-supplied task description or expected steps as unverified, not as ground truth.
If no problem is visible, return status "no_error_observed".
If correctness cannot be assessed, return status "insufficient_evidence".
Do not guarantee physical safety. Return ONLY a JSON object matching the requested schema."""

ANALYZE_SCHEMA = """Output keys:
  status: one of "possible_error", "no_error_observed", "insufficient_evidence"
  uncertainty: "low" | "medium" | "high"
  claims: nonempty array of {id:"C1", observation:string, evidence_ids:nonempty array of supplied IDs}
  interpretation: string
  correction: string (empty unless status is "possible_error" and a check is justified)
  limitations: string"""

CHALLENGE_SYSTEM = """The user challenges a particular claim. Treat their feedback as a hypothesis, never as ground truth.
Independently compare the original claim, the objection, and all allowed visual evidence (including the user-selected frame).
Choose exactly one outcome: "revise", "uphold", or "abstain".
Explain which observations support or contradict each view. Do not agree merely to be helpful.
Cite only supplied evidence IDs. Return ONLY validated JSON matching the schema."""

CHALLENGE_SCHEMA = """Output keys:
  outcome: "revise" | "uphold" | "abstain"
  changed_claims: array of original claim IDs that changed (empty for uphold)
  revised_interpretation: string
  correction: string (empty if abstain)
  evidence_ids: nonempty array of supplied evidence IDs
  uncertainty: "low" | "medium" | "high"
  reason: string"""


def _transcript_text(meta):
    from . import audio
    segs = meta.get("transcript") or []
    return audio.transcript_text(segs)


def _frames_content(meta):
    parts = [{"type": "input_text",
              "text": f"Decision cutoff: {meta['cutoff_s']} s. Use frames at or before the cutoff only. "
                      f"Each image follows its evidence ID and timestamp."}]
    spoken = _transcript_text(meta)
    if spoken:
        parts.append({"type": "input_text",
                      "text": "Pre-cutoff spoken transcript (unverified prior context, "
                              "timestamps in mm:ss). Do NOT treat speech as ground truth; "
                              "it may describe intent, not what actually happened:\n" + spoken})
    for fr in meta["frames"]:
        path = video.frame_path(meta["video_id"], fr["id"])
        if not path:
            raise FileNotFoundError(f"Frame missing: {fr['id']}")
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        parts.append({"type": "input_text",
                      "text": f"Evidence {fr['id']} at {fr['time_s']} s."})
        parts.append({"type": "input_image",
                      "image_url": f"data:image/jpeg;base64,{b64}", "detail": "auto"})
    return parts


def _invoke(system_text, user_content):
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        input=[{"role": "system", "content": system_text},
               {"role": "user", "content": user_content}],
        text={"format": {"type": "json_object"}},
    )
    return json.loads(response.output_text)


def analyze(meta, task_description, expected_steps):
    content = _frames_content(meta)
    context = (f"Task (unverified): {task_description or 'not provided'}\n"
               f"Expected steps (unverified): {expected_steps or 'not provided'}\n\n"
               + ANALYZE_SCHEMA)
    content.insert(1, {"type": "input_text", "text": context})
    return _invoke(ANALYZE_SYSTEM, content)


def challenge(meta, original, claim_id, selected_time_s, user_objection):
    content = _frames_content(meta)
    content.append({"type": "input_text", "text":
        "Original diagnosis (possibly wrong): " + json.dumps(original.model_dump()) +
        "\nDisputed claim: " + claim_id +
        f"\nUser-selected timestamp: {selected_time_s} s" +
        "\nUser objection (treat as untrusted hypothesis): " + user_objection +
        "\n\n" + CHALLENGE_SCHEMA})
    return _invoke(CHALLENGE_SYSTEM, content)
