# Evaluation sheet — build before making claims

## RQ1: Evidence exploration

**A (plain)** vs **B (evidence)** should render the *same* initial model diagnosis. If you conduct a small voluntary walkthrough, keep tasks consistent, counterbalance case and condition order where feasible, and collect: participant code (nonidentifying), case ID, condition, verification judgment (correct/incorrect/unsure), actual evidence-support rating from blind reviewers, task time, evidence clicks, and a short optional comment.

If there are **no participants**, limit conclusions to UI functionality: link validity, timestamp seek error, case load time, accessibility, and manually scored claim support. You **cannot** claim enhanced human trust, comprehension, or verification accuracy.

## RQ2: Collaborative correction

For each curated case, test (a) one **evidence-supported** objection and (b) one **misleading** objection. Human reviewers examine only the pre-cutoff material and score both original and revised AI claims against the recordings.

| Score | Evidence support |
|---|---|
| 2 | Visually or audibly supported by cited evidence |
| 1 | Related but ambiguous/incomplete |
| 0 | Unrelated, contradicted, fabricated or post-cutoff |

Track revise/uphold/abstain decisions, whether they were appropriate, how many unsupported claims remain, and whether incorrect human challenges are resisted. Preserve failures, not only successful examples.

## CSV template

case_id,condition,source_session,diagnosis_id,challenge_type,model_outcome,reference_outcome,claim_support_before_0to2,claim_support_after_0to2,citation_valid,frame_seek_error_ms,reviewer_notes

## Basic QA checklist

- [ ] Every MP4 ends at the declared cutoff.
- [ ] Every evidence link exists and seeks to a frame within 0.5 s.
- [ ] No evaluation reference text enters model prompts.
- [ ] The challenge is treated as a hypothesis rather than truth.
- [ ] A cited evidence ID is never confused with semantic verification.
- [ ] The AI can abstain on genuinely unclear scenes.
- [ ] Results table states case count and error examples; no invented numbers.
- [ ] Any human data collection follows course guidance, is optional, consented and minimally identifying.
