# Roadmap Restructure — Design

**Status:** Approved
**Date:** 2026-09-27
**Repo:** argocd-gitops-plugin

## Background

`docs/ROADMAP.md` was written before the plugin went public: a fixed sequence of version-numbered milestones (v0.6 = secrets, v0.7 = multi-env, v0.8 = rollback/evals, v0.9 = docs, v1.0 = a Definition-of-Done checklist), each with pre-decided implementation choices, sourced from a single internal "CTO assessment." Now that v0.6.0 is public (PR #14 merged, tagged, released), the author expects real feature requests and usage reports — people use Argo CD in ways the author's own experience doesn't cover — and doesn't want a fixed order or baked-in implementation choices standing in the way of following that feedback.

## Design

**Structure.** Replace the v0.5→v1.0 sequence with three unordered buckets:
- **Now** — what's actively being built.
- **Next** — high-confidence candidates.
- **Later** — worth keeping, not prioritized.

No bucket item carries a version number. A version is decided only when something actually ships (as `CHANGELOG.md` already does).

**Entries.** Each item is a one- or two-line pitch — the problem it solves, why it might matter — with no baked-in implementation choice. The mechanism is decided in brainstorming at pickup time, informed by whoever asked.

**Dropped:** the CTO-assessment framing and item numbers, S/M/L sizing, the baseline-commit line, per-milestone "gate" checklists, the sequencing table, and the v1.0 Definition-of-Done checklist. No fixed 1.0 feature set is promised.

**Kept:**
- The "out of scope" list (Flux support, cost/policy scaffolding, etc.), as a flat list, not versioned.
- The process note: a real feature still goes through brainstorming → plan → build → live dogfood → PR before it ships. This describes how the maintainer works, not a promise about timing.
- A new feedback-intake line: "Want something changed or added? Open a GitHub Issue — it becomes a Next/Later candidate."

## Content mapping (old → new)

| Old milestone | New bucket | Compressed pitch |
|---|---|---|
| v0.5 (done, shipped) | — | Dropped — already shipped, lives in CHANGELOG.md |
| v0.6 Secrets (ESO) | Next | "Secrets management: a GitOps repo the plugin produces still needs a hand-created Secret today." |
| v0.7 Multi-env / promotion | Next | "Multi-environment promotion: today's scaffold is single-env; dev→prod promotion is the point of GitOps." |
| v0.8.1 Rollback | Next | "Rollback: a proven way to get a broken app back to its last-good state." |
| v0.8.2 Agent hardening | Later | "`argocd-onboarder` proven fully unattended end-to-end on a live cluster." |
| v0.8.3 Skill-triggering evals | Later | "A reproducible baseline for whether Claude picks the right skill for a given request." |
| v0.8.4 External couplings | Later | "Document/pin the plugin's external dependencies (grafana.com API, chart repos)." |
| v0.9.1 Example repo | Later | "A clean, CI-verified example repo for newcomers (not the maintainer's own messy dogfood repo)." |
| v0.9.2 Quickstart | Later | "A 10-minute quickstart doc, copy-pasteable, verified by CI." |
| v0.9.3 Marketplace/install | — | Dropped — shipped in v0.6.0 |
| v0.9.4 Full regression dogfood | Later | "A from-scratch, no-undocumented-step run of the whole plugin on a fresh repo and cluster." |
| v1.0 DoD checklist | — | Dropped entirely |
| Out of scope list | Kept, flat | Unchanged content, no version framing |

## Self-review

- **Placeholders:** none.
- **Internal consistency:** the mapping table accounts for every old milestone; nothing silently disappears without a note.
- **Scope:** single file, no code — implementation is a straight rewrite, not a multi-task plan.
- **Ambiguity:** "Now" bucket may be empty at write time (nothing is actively being built the moment this is written) — the new roadmap says so explicitly rather than leaving it blank with no explanation.
