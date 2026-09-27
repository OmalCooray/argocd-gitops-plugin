---
name: argocd-sync
description: Drive an Argo CD app all the way to Synced + Healthy + actually-functioning — trigger the sync, watch it in bounded steps, and on any stall diagnose → fix in git (PR) → re-sync until it converges or reports a clear blocker. Ends with a functional check, not just pod status.
argument-hint: "<app-name> [environment-name] [--context <name>]"
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

0. **Resolve the target:** follow `${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`; use its `CTX` and `ARGOCD_NS` in every command below. Accept an optional `--context <name>` argument.
- The app's git revision is already on the tracked branch (its deploy PR is
  merged). If not, tell the user to merge it first (or run `/argocd-deploy`).
- A reachable cluster (`kubectl`); `argocd` CLI optional. If the cluster is unreachable, stop with the one-line message from `target-resolution.md` step 5 — do not continue.

## Steps

1. Load skills `argocd-rollout` and `argocd-troubleshooting`. Follow the rollout
   loop exactly.
2. Read the app's live state once:
   `kubectl --context "$CTX" -n "$ARGOCD_NS" get application <app> -o json` — capture destination namespace,
   `spec.sources[]` (or `spec.source`), `status.sync.status`, `status.health.status`,
   `status.sync.revisions[]` (multi-source; `status.sync.revision` is null there) and `status.operationState`.
   If the Application does not exist yet, refresh its parent first: annotate `root-<env>` with
   `argocd.argoproj.io/refresh=hard`, then re-read (allow one 30 s wait).
3. **Nothing-to-do exit.** If it is `Synced` + `Healthy`, has no running operation, and
   every `status.sync.revisions[]` (or `revision`) equals the tracked branch's HEAD
   (`git ls-remote <repo-url> <targetRevision>`), print
   `<app>: already Synced/Healthy at <sha> — nothing to do` and jump to step 5 (functional check). Do **not** trigger anything.
4. Checkpoint: `> About to trigger a sync of <app> on "$CTX". Proceed?` Then run the rollout loop:
   trigger (refresh first) → bounded watch (stated ceiling, **12 minutes total wall-clock across all cycles**) →
   on stall, troubleshoot → fix as a git change → PR (checkpoint) → merge (checkpoint) →
   clear any deadlocked op → re-sync. Cap the fix cycles at 4.
5. When Argo CD reports `Synced/Healthy`, run the **functional check** for the
   app type (rollout skill's table) — an actual request / query, not pod status.
6. Report per the rollout skill's format: converged (with the fix PRs and what
   the functional check confirmed) or not (with every blocker found and what a
   human needs to decide).

## Notes

- Fixes are git changes only. Allowed direct cluster actions: trigger/clear a
  sync, `annotate refresh`, create a missing out-of-band Secret. Never edit /
  scale / patch a workload, disable a probe, or drop replicas to force green.
- If a fix needs something you can't provide (a real secret value, a decision
  between two valid approaches, a second app), stop and ask — don't guess.
