# Interaction contract — every argocd-gitops-plugin command

The person is watching in the Claude Code UI. Keep the work legible and keep them
in control of the big moves. This overrides any default toward "just do it".

## Always

1. **Announce the step before doing it.** One line: what and why.
   `> Installing Argo CD (argo/argo-cd chart 10.8.4) into namespace argocd.`

2. **Show the command, then its meaningful output.** Put commands in a fenced
   block. After running, show the lines that matter (status, names, errors) —
   not a 200-line dump.

3. **Run long operations in the foreground.** Never launch a silent background
   job for an install, a sync, or a wait. If something takes minutes:
   - say so up front (`> This install takes ~3 min; watching it now.`)
   - run it in the foreground so its output streams
   - if you must wait on a condition, do a **bounded** check (a few probes over
     a stated window), printing one status line per probe, and stop as soon as
     it's ready or clearly stuck — never an open-ended loop.

4. **No polling loops for health.** Inspect once, decide progressing-vs-stuck
   (see `argocd-troubleshooting`), report. If it's still legitimately
   progressing, say what it's waiting on and hand back — don't sit and spin.

5. **End with a plain-text summary.** What changed (files, branches, PRs,
   cluster objects), current state, and the single next action.

## Checkpoint before (ask, one line, wait for yes)

- installing anything onto a cluster (`helm install/upgrade`, `kubectl apply` of
  an operator or CRDs)
- triggering or forcing an Argo CD sync, or terminating a sync operation
- `kubectl delete` of anything, or a prune
- `git push` + opening a PR (show the branch name and PR title first)
- creating a GitHub repo

A checkpoint is `> About to <X>. Proceed?` — not a paragraph. If the person
already said "go ahead and don't ask", honour that for the rest of the run.

## Never

- background an install/sync/wait and move on
- `sleep` in a loop waiting for Healthy
- apply a cluster workaround (`kubectl edit`, `kubectl scale`, `kubectl patch` of
  a workload) to paper over a values bug — the fix is a git change
- dump full manifests / full logs when three lines identify the issue
