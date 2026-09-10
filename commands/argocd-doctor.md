---
name: argocd-doctor
description: Diagnose a stuck / Degraded / OutOfSync Argo CD application — inspect the app status and resource tree once (no waiting loops), find the failing object, name the root cause and the fix. Read-only; proposes a git change, does not apply workarounds to the cluster.
argument-hint: "[app-name]  (omit to triage every app in the env)"
---

Diagnose why an Argo CD app is not `Synced` / `Healthy`.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each inspection step, show the command + the three lines that matter,
one-shot (never poll), checkpoint before the two allowed unblock actions, end
with the root-cause / evidence / fix summary.

## Inputs

- `$1` — the app to diagnose. If omitted, list every Argo CD app and diagnose
  each that is not `Synced/Healthy`.

## Preconditions

- A reachable cluster (`kubectl`), and ideally the `argocd` CLI logged in.
- If `mcp__argocd__*` tools are present, use them for the read-only queries.
- No cluster? Run in offline mode — ask the user for the dumps listed in the
  `argocd-troubleshooting` skill.

## Steps

1. Load the skill `argocd-troubleshooting` and follow it.
2. **Do not poll.** Inspect state once. Decide progressing vs stuck using the
   skill's test (time on the current `operationState.message`, pod phases). If
   genuinely still progressing (images pulling < ~2 min, init containers
   running), say so and stop — there is nothing to fix yet.
3. If stuck: walk `status.resources[]` to the worst object, `describe` it, read
   its Events, then its pods' Events / logs / previous-crash logs / init-container
   logs.
4. Match the failure signature (skill's table). State:
   - **Root cause** — one sentence, concrete (`image.tag "v0.61.1.x" does not
     exist`, not "image problem").
   - **Evidence** — the exact event / log line.
   - **Fix** — the values key or manifest change, with the suggested value, and
     which file in the repo it goes in.
   - **One-off cluster action** — only if needed to unblock (create a missing
     Secret, clear a stuck sync operation). Never a `kubectl edit` workaround.
5. If `--fix` was passed (and the fix is a repo change), make it on a branch and
   open a PR the way `/argocd-deploy` does; otherwise just report.
6. After the user applies the fix and syncs, re-run once to confirm.

## Output

For each diagnosed app:

```
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
