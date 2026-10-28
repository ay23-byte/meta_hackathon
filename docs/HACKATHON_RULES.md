# Hackathon requirements — verified vs. unverified

Read on 26 October 2026. This file exists so the team never guesses at a
rule. Anything below marked "unverified" comes from community summaries or
Discord and must be confirmed in the participant portal before submission.

## Verified from the official pages

Source A — official event page, Meta / Cerebral Valley:
<https://cerebralvalley.ai/e/meta-ai-developer-hackathon>

Source B — Hackathon Terms & Conditions ("Official Rules") and Event Waiver:
<https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver>

| Requirement | Verified fact | Source |
| --- | --- | --- |
| Participation | Application required; up to 20,000 accepted participants | A, B |
| Build window | Hackathon runs 26 Oct – 4 Nov 2026 (virtual) | A |
| Submission deadline | 4 Nov 2026, 9:00 PM ET, via the Cerebral Valley submission portal | A (Key Dates), B (portal link) |
| Eligibility | 18+ and age of majority; excluded jurisdictions and sanctioned parties; not Meta/Cerebral Valley staff or government-affiliated; household members excluded | B |
| Technology | Participants build with Meta AI products (Muse Spark, Glimmer, SAM 3, and others named on the event page) | B |
| Credits | Selected participants receive $150 in Meta Model API credits; Baseten/Modal/Fireworks also offer partner credits to selected participants | B, A |
| Tracks | Two: Indie Developer (teams up to 4) and Startup; one track per project; teams appoint a Representative | B |
| Themes | "Build for Your World" and "Push the Frontier" (the latter explicitly includes accelerating a scientific experiment) | A |
| Judging weights | Impact 30%, Use of Meta AI Tooling 25%, Technical Depth & Execution 20%, Demo 25% | B |
| Demo | Judges assess a working, impressive demo that holds up live **and the quality of the demo video** | B |
| Originality | Submission must be the entrant's original work product; open-source components are allowed when their licenses are followed | B |
| Video length | **Not specified** in the Official Rules text read on 26 Oct | B |
| Repo visibility | **Not specified** in the Official Rules text read on 26 Oct | B |

## Unverified — community / Discord claims, confirm before relying on them

The following appear in third-party summaries and a community build log
(<https://github.com/sholaola23/meta-hackathon-2026>), not in the official
text we could read. Treat them as guidance, not rules:

- a three-minute maximum demo video;
- the repository must be public at submission;
- only work created during 26 Oct – 4 Nov may be shown in the demo;
- a dated Baseten model identifier such as
  `meta-models/muse-spark-open-1026` for hackathon credits (official Meta
  and Baseten pages list `meta-models/muse-spark-open`);
- an explicit list of discouraged "anti-projects".

Whatever the final ruling on originality, keep a dated build log so the
work done in the window is demonstrable. This repository's git history is
the easiest evidence — do not rewrite or squash it before submission.

## How LabLens AI maps to the four weighted criteria

This is a **self-assessment, not a score from any judge**.

| Criterion | Weight | What the project can show | Honest caveat |
| --- | --- | --- | --- |
| Impact | 30% | Reproducible scientific analysis workflow; explicit cleaning, uncertainty and provenance caveats; downloadable audit record | No measured user adoption, no time-saved study — do not claim one |
| Use of Meta AI Tooling | 25% | Muse Spark Open via Baseten with developer-message instructions, JSON mode, strict schema validation, evidence-linked claims, and a context-hash binding | Live provider round-trip still needs a key in this environment |
| Technical Depth & Execution | 20% | Numerically stable centred OLS plus five model families and weighted fits, 426 offline tests, AppTest UI tests, 13-tool bounded agent, CLI/dashboard shared core, lint-clean Linux/Windows CI | CSV/TSV input only; no calibrated instrument uncertainty; no causal inference |
| Demo | 25% | Primary `general_app.py` dashboard, real-time plots, three exports, seven reproducible A-E agent cases, honest provider status and an explicitly labelled OFFLINE MOCK fallback | Record the video live; never present the mock as a live AI result |

## Pre-submission checklist

- [ ] Confirm you are an accepted participant and have accepted the Official Rules.
- [ ] Re-read the rules in the participant portal (they can be modified).
- [ ] Confirm your track, theme, team members and Representative.
- [ ] Confirm the exact submission deadline in your local timezone.
- [ ] Confirm whether a public repo and a demo video length limit apply.
- [ ] Verify the Meta technology requirement for your account's credits and model ID.
- [ ] Record the demo video with no API key visible; keep it within any stated limit.
- [ ] Submit via the Cerebral Valley portal before the deadline.
