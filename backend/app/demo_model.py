"""Deterministic offline stand-in used when EVIDENCELENS_MODE=demo.

This is NOT an AI model and its output is NOT evidence of real capability.
It exists only so the upload -> analyze -> challenge -> revision flow is
exercisable (and testable) without an API key or network. It builds its
response from the actual frames extracted from the uploaded video, so the
timestamps and evidence IDs are real for that upload even though the wording
is fixed. The UI labels this mode clearly.
"""


def analyze(meta, task_description, expected_steps):
    frames = meta["frames"]
    # Cite the first and a middle frame so evidence links point at real moments.
    first = frames[0]["id"]
    mid = frames[len(frames) // 2]["id"]
    evidence_ids = sorted({first, mid})
    task = (task_description or "the recorded task").strip()
    spoken = bool(meta.get("transcript"))
    audio_note = (" A pre-cutoff spoken transcript was available and would inform a live analysis."
                  if spoken else " No usable speech was found in this clip.")
    return dict(
        status="possible_error",
        uncertainty="high",
        claims=[dict(
            id="C1",
            observation=f"A step in {task} appears inconsistent between the earlier and later sampled frames.",
            evidence_ids=evidence_ids,
        )],
        interpretation="An action may deviate from the expected procedure; this is a tentative, demo-mode reading.",
        correction="Re-check the highlighted step against the intended sequence before continuing.",
        limitations="Scripted demo output for interface testing only. Switch to live mode for a real model analysis." + audio_note,
    )


def challenge(meta, original, claim_id, selected_time_s, user_objection):
    frames = meta["frames"]
    # Pick the extracted frame nearest the user's selected timestamp.
    nearest = min(frames, key=lambda f: abs(f["time_s"] - selected_time_s))
    base = original.claims[0]
    cited = sorted({base.evidence_ids[0], nearest["id"]})
    lower = user_objection.lower()

    # Deterministic heuristic so all three outcomes are reachable in demo mode:
    #   placement/position/hole/wrong -> revise
    #   correct/fine/aligned/right    -> uphold
    #   otherwise                     -> abstain
    if any(k in lower for k in ("placement", "position", "hole", "wrong", "misaligned")):
        return dict(
            outcome="revise", changed_claims=[base.id],
            revised_interpretation="On the selected frame the issue looks like placement rather than the originally stated cause.",
            correction="Recheck the position against the earlier reference frame before proceeding.",
            evidence_ids=cited, uncertainty="medium",
            reason="Demo heuristic: the objection points to placement and the selected frame is consistent with that reading.")
    if any(k in lower for k in ("correct", "fine", "aligned", "right", "ok")):
        return dict(
            outcome="uphold", changed_claims=[],
            revised_interpretation="The selected frame does not overturn the original observation.",
            correction="Original suggested check still applies; verify before continuing.",
            evidence_ids=cited, uncertainty="medium",
            reason="Demo heuristic: an objection is not accepted automatically; the cited frames still support the original claim.")
    return dict(
        outcome="abstain", changed_claims=[base.id],
        revised_interpretation="The available frames do not establish the state clearly enough to revise or uphold.",
        correction="",
        evidence_ids=cited, uncertainty="high",
        reason="Demo heuristic: insufficient visible support; a clearer view is needed.")
