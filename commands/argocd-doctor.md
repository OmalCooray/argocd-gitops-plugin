---
name: argocd-doctor
description: Diagnose a stuck / Degraded / OutOfSync Argo CD application — inspect the app status and resource tree once (no waiting loops), find the failing object, name the root cause and the fix. Read-only; proposes a git change, does not apply workarounds to the cluster.
argument-hint: "[app-name]  (omit to triage every app in the env) [--fix] [--context <name>]"
---

Diagnose why an Argo CD app is not `Synced` / `Healthy`.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each inspection step, show the command + the three lines that matter,
one-shot (never poll), checkpoint before the two allowed unblock actions, end
with the root-cause / evidence / fix summary.

## Inputs

- `$1` — the app to diagnose. If omitted, list every Argo CD app and diagnose
  each that is not `Synced/Healthy`. Triage-all only sees **live** apps: also run the
  missing-app check from `/argocd-audit` and mention any app declared in
  `environments/*/apps/` but absent from the cluster.

## Preconditions

0. **Resolve the target:** follow `${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`; use its `CTX` and `ARGOCD_NS` in every command below. Accept an optional `--context <name>` argument.
- A reachable cluster (`kubectl`), and ideally the `argocd` CLI logged in.
- No cluster? Run in offline mode — ask the user for the dumps listed in the
  `argocd-troubleshooting` skill.

## Steps

1. Load the skill `argocd-troubleshooting` and follow it.
2. **Unknown app.** If `kubectl --context "$CTX" -n "$ARGOCD_NS" get application <app>` says
   NotFound, print `<app> not found`, list the live apps
   (`kubectl --context "$CTX" -n "$ARGOCD_NS" get applications`), and check whether
   `environments/*/apps/<app>.yaml` declares it. If it is declared but not live, say so and
   point to `/argocd-audit`. Stop.
3. **Healthy branch.** If `Synced` + `Healthy`, no operation running and no `conditions`,
   print `<app>  Synced/Healthy — healthy — nothing to fix` and stop (skip the
   `/argocd-sync` hand-off).
4. **Do not poll.** Inspect state once. Decide progressing vs stuck using the
   skill's test (time on the current `operationState.message`, pod phases). If
   genuinely still progressing (images pulling < ~2 min, init containers
   running), say so and stop — there is nothing to fix yet.
5. If stuck: walk `status.resources[]` to the worst object, `describe` it, read
   its Events, then its pods' Events / logs / previous-crash logs / init-container
   logs.
6. Match the failure signature (skill's table). State:
   - **Root cause** — one sentence, concrete (`podinfo.image.tag "6.999.999"`
     does not exist, not "image problem"). Note an app with a bad image tag stays
     `Synced/Progressing` (not `Degraded`) until the Deployment's 600 s
     `progressDeadlineSeconds` expires, so judge by pod events, not the health colour.
   - **Evidence** — the exact event / log line.
   - **Fix** — the values key or manifest change, with the suggested value, and
     which file in the repo it goes in. For a wrapper chart every key nests under the
     dependency name: `<chart>.image.tag`, in `environments/<env>/values/<app>.yaml`
     (per-env) or `charts/<app>/values.yaml` (all envs) — a bare `image.tag` silently
     does nothing. Read `argocd-repo-conventions` to pick the file.
   - **One-off cluster action** — only if needed to unblock: create a missing
     out-of-band Secret, or clear a **deadlocked sync** (the sync is
     "waiting for healthy state of X" and X can't be healthy until the merged fix
     applies — see `argocd-troubleshooting` → "Clearing a deadlocked sync"). Never
     a `kubectl edit` / `scale` / workload-`patch` workaround.
7. If `--fix` was passed (and the fix is a values change), do it in this order:
   1. `git switch -c fix/<app>-<slug>`.
   2. Edit exactly one values file (the one chosen above).
   3. Verify it renders locally, on a temp copy so the working tree's `Chart.lock` is not
      rewritten: `tmp=$(mktemp -d) && cp -r charts/<app> "$tmp/" && helm dependency build "$tmp/<app>"`,
      then `helm template <app> charts/<app> -n <dest-namespace> -f environments/<env>/values/<app>.yaml`
      (run against the temp copy) must render without error.
   4. Commit the one-file change.
   5. **Checkpoint:** `> About to push fix/<app>-<slug> and open a PR. Proceed?`
   6. Push, then open the PR (body: root cause, evidence line, the one-line diff). Follow
      `${CLAUDE_PLUGIN_ROOT}/references/no-remote-fallback.md` when present, otherwise
      print the branch, PR body and exact `git push` / `gh pr create` commands and stop.

   Without `--fix`, just report.
8. After the fix is merged, re-sync and re-run once to confirm — or, to drive it
   the rest of the way to Healthy + functioning, hand off to `/argocd-sync <app>`.

## Output

For each diagnosed app:

```
inspected: <CTX> / <ARGOCD_NS> → dest ns <ns>
<app>  <sync>/<health>  — <progressing | STUCK>
root cause : <one sentence>
evidence   : <event or log line>
fix        : <file> → <key> = <value>
unblock    : <one-off command, or "none">
```

## Notes

- **Read-only against the cluster** except the two allowed unblock actions
  (create a missing out-of-band Secret; clear a stuck sync operation). Everything
  else is a git change the user reviews.
- This is the triage half of the old hand-run reconcile script, plus a fix.
