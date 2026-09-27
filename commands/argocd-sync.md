---
name: argocd-sync
description: Drive an Argo CD app all the way to Synced + Healthy + actually-functioning — refresh, then sync only if needed, watch it in bounded steps, and on any stall diagnose → fix in git (PR) → re-sync until it converges or reports a clear blocker. Ends with a functional check, not just pod status.
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
   `argocd.argoproj.io/refresh=hard`, then re-read (allow one 30 s wait). A `refresh=hard`
   annotation starts no operation (it only re-reads git), so it is exempt from the checkpoint;
   the checkpoint in step 4 gates operations that change the cluster. If the Application still
   does not exist 30 s after refreshing `root-<env>`, print
   `<app> was not created by root-<env>: check that environments/<env>/apps/<app>.yaml is merged and root-<env> is Synced` and stop.
3. **Nothing-to-do exit.** If it is `Synced` + `Healthy` and has no running operation, compare the
   synced revision(s) with what git/the chart repo currently has. Single-source app: compare
   `status.sync.revision`. Multi-source app: `status.sync.revisions[i]` corresponds to `spec.sources[i]`.
   For a **git** source (this plugin's wrapper-chart apps: the `charts/<app>` source and the `ref: values`
   source both point at the GitOps git repo) compare the revision to the tracked ref: branch/`HEAD` →
   `GIT_TERMINAL_PROMPT=0 timeout 20 git ls-remote <repoURL> <targetRevision>` (first column); tag → use the peeled line
   (`refs/tags/<t>^{}`) if present; a 40-hex SHA `targetRevision` → compare directly (no ls-remote).
   For a **Helm-repo** source compare `revisions[i]` to its `targetRevision` chart version.
   If `ls-remote` fails or exits non-zero (the guard stops a private repo from prompting and hanging) (private repo without credentials, no network), say so and treat the comparison
   as unknown: do NOT take the nothing-to-do exit, continue to step 4.
   If every source matches, print `<app>: already Synced/Healthy at <sha> — nothing to do` and jump to
   step 5 (functional check). Do **not** trigger anything.
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

- After a fix PR is merged, Argo CD can take up to ~3-4 minutes to notice it (observed live: 3m40s) unless refreshed. The first probes can still show the old state: refresh first (already the default trigger) and do not treat unchanged state in the first 1–2 probes as "stuck".

- Fixes are git changes only. Allowed direct cluster actions: trigger/clear a
  sync, `annotate refresh`, create a missing out-of-band Secret. Never edit /
  scale / patch a workload, disable a probe, or drop replicas to force green.
- If a fix needs something you can't provide (a real secret value, a decision
  between two valid approaches, a second app), stop and ask — don't guess.
