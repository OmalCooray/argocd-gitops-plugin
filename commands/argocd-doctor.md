---
name: argocd-doctor
description: Diagnose a stuck / Degraded / OutOfSync Argo CD application — inspect the app status and resource tree once (no waiting loops), find the failing object, name the root cause and the fix. Read-only against the cluster; with --fix it also creates a local branch and, after a checkpoint, pushes it and opens a PR. Does not apply workarounds to the cluster.
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
2. **Unknown app.** (An unreachable cluster is already stopped by target resolution before
   this step, so NotFound here really means the app is not in `$ARGOCD_NS`.) If
   `kubectl --context "$CTX" -n "$ARGOCD_NS" get application <app>` says NotFound, print
   `<app> not found`, list the live apps
   (`kubectl --context "$CTX" -n "$ARGOCD_NS" get applications`), and check the repo:
   - `environments/*/apps/<app>.yaml` declares it but it is not live: say "declared but not live" and point to `/argocd-audit`.
   - `charts/<app>` exists but no `environments/*/apps/<app>.yaml`: say "`<app>` is in the
     catalog but not deployed to any environment — `/argocd-deploy <app> <env>`".

   Stop.
3. **Healthy branch.** Healthy = `Synced` AND `Healthy` AND no running operation AND
   no `conditions`. Print the `inspected:` line first, then
   `<app>  Synced/Healthy — healthy — nothing to fix`, and stop (skip the `/argocd-sync`
   hand-off). A restart count alone does not make an app unhealthy; if a container
   restarted in the last hour but is Ready, add a one-clause mention. If `conditions` are
   present, print each (type/message) and continue to step 4.
4. **Do not poll.** Inspect state once. Decide progressing vs stuck using the
   skill's test (time on the current `operationState.message`, pod phases). If
   genuinely still progressing (images pulling < ~2 min, init containers
   running), say so and stop — there is nothing to fix yet — unless a pod is
   Running-but-not-Ready with an evident error (see the skill's Running-but-not-Ready
   note): diagnose that now.
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
     which file in the repo it goes in. `<chart>` is the wrapper
     `charts/<app>/Chart.yaml` `dependencies[0].name` (it may differ from the app name); an
     OWN-APP chart has no `dependencies`, so its keys are top-level (no prefix). For a
     wrapper chart every key nests under `<chart>`, e.g. `<chart>.image.tag` — a bare
     `image.tag` silently does nothing. Default file: the env overlay
     `environments/<env>/values/<app>.yaml`, unless the bug is in the shared base
     `charts/<app>/values.yaml` (affects all envs). Read `argocd-repo-conventions` if unsure.
   - **One-off cluster action** — only if needed to unblock: create a missing
     out-of-band Secret, or clear a **deadlocked sync** (the sync is
     "waiting for healthy state of X" and X can't be healthy until the merged fix
     applies — see `argocd-troubleshooting` → "Clearing a deadlocked sync"). Never
     a `kubectl edit` / `scale` / workload-`patch` workaround.
7. If `--fix` was passed (and the fix is a values change), do it in this order:
   1. Require a clean tree: `git status --porcelain` must be empty, otherwise stop and ask.
   2. `git switch -c fix/<app>-<slug>`, where `<slug>` is the kebab-case root cause
      (e.g. `bad-image-tag`).
   3. Edit exactly one values file (the one chosen above).
   4. Render on a temp copy so the working tree's `Chart.lock` is not rewritten:
      ```bash
      tmp="$(mktemp -d)"; cp -r "charts/<app>" "$tmp/"; helm dependency build "$tmp/<app>"
      helm template <app> "$tmp/<app>" -n <dest-namespace> -f "environments/<env>/values/<app>.yaml" | grep -n 'image:'
      rm -rf "$tmp"
      ```
      It must render without error, and the grep must show the NEW value (adapt the
      pattern to the changed key). If the old value still shows, the key is at the wrong nesting: fix it.
   5. `git add environments/<env>/values/<app>.yaml`, then commit.
   6. **Checkpoint:** `> About to push fix/<app>-<slug> and open a PR. Proceed?`
   7. Push, then open the PR (body: root cause, evidence line, the one-line diff). Follow
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
  else is a git change the user reviews. With `--fix` it also creates a local branch
  and, after a checkpoint, pushes it and opens a PR.
- This is the triage half of the old hand-run reconcile script, plus a fix.
