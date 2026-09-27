# Roadmap Restructure — Design

**Status:** Approved
**Date:** 2026-09-27
**Repo:** argocd-gitops-plugin

## Background

`docs/ROADMAP.md` was written before the plugin went public: a fixed sequence of version-numbered milestones (v0.6 = secrets, v0.7 = multi-env, v0.8 = rollback/evals, v0.9 = docs, v1.0 = a Definition-of-Done checklist), each with pre-decided implementation choices, sourced from a single internal "CTO assessment." Now that v0.6.0 is public (PR #14 merged, tagged, released), the author expects real feature requests and usage reports — people use Argo CD in ways the author's own experience doesn't cover — and doesn't want a fixed order or baked-in implementation choices standing in the way of following that feedback.

## Design

**Structure.** Replace the v0.5→v1.0 sequence with one bucket for now:
- **Now** — what's actively being built (may be empty; that's stated explicitly, not left blank with no explanation).

No pre-filled "Next" or "Later" candidates. The old feature ideas (secrets, multi-env, rollback, evals, docs/quickstart) are not carried forward as a backlog — they're dropped entirely rather than parked. Direction from here comes only from what people actually ask for via GitHub Issues; the roadmap starts from real signal, not from the author's pre-existing guesses about what matters. `Next`/`Later` buckets can be reintroduced once there's real feedback to sort into them.

No bucket item carries a version number. A version is decided only when something actually ships (as `CHANGELOG.md` already does).

**Dropped:** the CTO-assessment framing and item numbers, S/M/L sizing, the baseline-commit line, per-milestone "gate" checklists, the sequencing table, and the v1.0 Definition-of-Done checklist. No fixed 1.0 feature set is promised.

**Kept:**
- The "out of scope" list (Flux support, cost/policy scaffolding, etc.), as a flat list, not versioned.
- The process note: a real feature still goes through brainstorming → plan → build → live dogfood → PR before it ships. This describes how the maintainer works, not a promise about timing.
- A new feedback-intake line: "Want something changed or added? Open a GitHub Issue — it becomes a Next/Later candidate."

## Content mapping (old → new)

| Old milestone | New bucket | Note |
|---|---|---|
| v0.5 (done, shipped) | — | Dropped — already shipped, lives in CHANGELOG.md |
| v0.9.3 Marketplace/install | — | Dropped — shipped in v0.6.0 |
| v0.6 Secrets, v0.7 Multi-env, v0.8.1 Rollback, v0.8.2 Agent hardening, v0.8.3 Skill evals, v0.8.4 External couplings, v0.9.1 Example repo, v0.9.2 Quickstart, v0.9.4 Full regression dogfood | — | Dropped entirely, not parked in a bucket — these were the author's pre-existing guesses; they don't reappear until someone actually asks |
| v1.0 DoD checklist | — | Dropped entirely |
| Out of scope list | Kept, flat | Unchanged content, no version framing |

## Self-review

- **Placeholders:** none.
- **Internal consistency:** the mapping table accounts for every old milestone; nothing silently disappears without a note.
- **Scope:** single file, no code — implementation is a straight rewrite, not a multi-task plan.
- **Ambiguity:** "Now" bucket may be empty at write time (nothing is actively being built the moment this is written) — the new roadmap says so explicitly rather than leaving it blank with no explanation.
