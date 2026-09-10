---
name: argocd-sync
description: Drive an Argo CD app all the way to Synced + Healthy + actually-functioning — trigger the sync, watch it in bounded steps, and on any stall diagnose → fix in git (PR) → re-sync until it converges or reports a clear blocker. Ends with a functional check, not just pod status.
argument-hint: "<app-name> [environment-name]"
---

Take one Argo CD application from "declared in git" to "the app works". A deploy
is finished when the app is Healthy **and** a functional check passes — not when
the PR merges.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each step, one status line per watch check, checkpoint before merging
a fix PR or clearing a sync, no open-ended polling.

## Inputs

- `$1` — Argo CD Application name (required).
- `$2` — environment (optional; used to locate its files under
  `environments/<env>/`).

## Preconditions

- The app's git revision is already on the tracked branch (its deploy PR is
  merged). If not, tell the user to merge it first (or run `/argocd-deploy`).
- A reachable cluster (`kubectl`); `argocd` CLI optional. `mcp__argocd__*` tools
  used for reads if present.

## Steps

1. Load skills `argocd-rollout` and `argocd-troubleshooting`. Follow the rollout
   loop exactly.
2. Read the app's destination namespace and sources from
   `kubectl -n <argocd-ns> get application <app> -o json` (or the manifest in
   `environments/<env>/apps/<app>.yaml`).
3. Run the loop: trigger sync → bounded watch (stated ceiling) → on stall,
   troubleshoot → fix as a git change → PR (checkpoint) → merge (checkpoint) →
   clear any deadlocked op → re-sync. Cap the fix cycles at 4.
4. When Argo CD reports `Synced/Healthy`, run the **functional check** for the
   app type (rollout skill's table) — an actual request / query, not pod status.
5. Report per the rollout skill's format: converged (with the fix PRs and what
   the functional check confirmed) or not (with every blocker found and what a
   human needs to decide).

## Notes

- Fixes are git changes only. Allowed direct cluster actions: trigger/clear a
  sync, `annotate refresh`, create a missing out-of-band Secret. Never edit /
  scale / patch a workload, disable a probe, or drop replicas to force green.
- If a fix needs something you can't provide (a real secret value, a decision
  between two valid approaches, a second app), stop and ask — don't guess.
