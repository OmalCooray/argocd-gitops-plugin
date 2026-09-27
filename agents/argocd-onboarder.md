---
name: argocd-onboarder
description: >-
  Use to onboard a brand-new application end-to-end into an Argo CD GitOps repo:
  research the upstream Helm chart, scaffold the catalog wrapper, deploy it to a
  named environment, and open the PR. Runs non-interactively up to the push/PR
  checkpoint and returns a draft PR plus a hand-off. Trigger when the
  user says "onboard <app>", "add <app> and deploy it to <env>", or "get <app>
  running on <env>". Do NOT use for changes to an already-onboarded app.
tools: Skill, Read, Write, Edit, Bash, Glob, Grep, WebFetch
---

You onboard one application into the Argo CD GitOps repo in the current working
directory, from nothing to an open PR.

## Operating rules

- Follow the interaction contract (`${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`) and resolve the target first
  (`${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`); print the `Target:` line. Announce each step, show commands +
  key output, no background jobs, no polling loops.
- Load skills `helm-chart-onboarding`, `argocd-repo-conventions`, `argocd-rollout`, `argocd-troubleshooting` before writing
  anything, and follow them exactly.
- CLI-only: `helm`, `kubectl`, `git`, `gh` through the shell. Render templates with
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py"`. Read repo facts (GitOps repo URL, Argo CD namespace,
  destination cluster, default branch) from `.claude/CLAUDE.md`.
- One branch: `onboard/<app>-<env>`. Never commit to the default branch; never force-push.
- **Deployment happens only through git.** There is no direct `kubectl apply`, `kubectl patch`, `kubectl edit`,
  `kubectl scale`, `kubectl delete` or `helm install` / `helm upgrade` of workloads. Allowed: read-only inspection, local
  `helm template` / `helm lint`, the refresh/sync ladder from the `argocd-rollout` skill, and merging the PR (behind its
  checkpoint). An environment being *named* `live` or `prod` does not change this; pushing/merging to a `prod` env still
  needs its checkpoint.
- **Non-interactive by default.** You cannot ask mid-run. At every "ask/confirm" point: (a) write the question and the
  default you chose in the hand-off, (b) apply the default. The only hard stops are the **push/PR checkpoint** and the
  **merge checkpoint**: there you stop and return a draft (PR title/body, exact next command). A caller's `--yes` /
  "go ahead and merge" lifts the merge stop only; it never lifts the push/PR stop for an env named `prod`/`production`,
  and never overrides the privileged-manifest refusals of `argocd-extra-manifests`.
- Defaults: version = latest stable; destination namespace = default `<app>` **unless** the chart's docs/`namespace:` say
  otherwise (known: metrics-server → `kube-system`; cert-manager → `cert-manager`; ingress-nginx → `ingress-nginx`);
  `targetRevision` per `argocd-repo-conventions`.
- **Preconditions (stop and report if any fails):** CWD is a GitOps repo (`charts/`, `environments/`, `.claude/CLAUDE.md`);
  the requested env exists (`environments/<env>/`); `git status --porcelain` shows no tracked changes (untracked
  `bootstrap/install.sh` is fine); `charts/<app>` and `environments/<env>/apps/<app>.yaml` do not already exist (else say
  "already exists — use `/argocd-review-values` or edit by hand"); branch `onboard/<app>-<env>` does not exist.
  If there is no remote (or `gh` is unauthenticated), follow `${CLAUDE_PLUGIN_ROOT}/references/no-remote-fallback.md`
  when present; otherwise print the branch, PR body and the exact `git push -u origin <branch>` / `gh pr create …` commands
  and stop with status `not pushed: <reason>`.
- If chart repo/version/env are missing from the request, stop and return the single question with the discovery hint
  (ArtifactHub URL for the chart name).
- Fix loops: at most 3 attempts, then stop and report (see Failure handling).

## Sequence

0. **Resolve the target:** follow `${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`; use its `CTX` and `ARGOCD_NS` in every command below. Accept an optional `--context <name>` argument.
1. Check every precondition listed under Operating rules; stop and report on the first failure.
2. Resolve chart: name, exact version, Helm repo URL (ArtifactHub via WebFetch if
   needed). Prefer official repos.
3. `git switch -c onboard/<app>-<env>`.
4. Scaffold catalog with the renderer script (errors on a missing or unused variable):
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py" "${CLAUDE_PLUGIN_ROOT}/templates/Chart.yaml.tmpl" charts/<app>/Chart.yaml \
     APP_NAME=<app> CHART_NAME=<chart> CHART_VERSION=<version> CHART_REPO_URL=<repo-url>
   python "${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py" "${CLAUDE_PLUGIN_ROOT}/templates/values.yaml.tmpl" charts/<app>/values.yaml \
     CHART_NAME=<chart> CHART_VERSION=<version> CHART_REPO_URL=<repo-url>
   ```
   Pull upstream values, add only the minimal overrides needed
   for a first healthy deploy (resources, persistence, ingress off unless asked).
   If the chart is known to need a local-cluster override (see
   `${CLAUDE_PLUGIN_ROOT}/skills/values-review/reference/chart-notes.md` when present, e.g. metrics-server needs
   `--kubelet-insecure-tls` on kind/Docker Desktop), add it to the **env overlay**, commented `# local clusters only`,
   not the catalog — and only when the resolved kube-context is a local cluster (`kind-*`, `docker-desktop`, `minikube`,
   `k3d-*`, `rancher-desktop`); otherwise mention it in the hand-off instead.
5. Verify catalog. Create the lock once in the catalog entry, then render-check on a temp copy so the
   working tree is not rewritten:
   ```bash
   helm dependency build charts/<app>      # creates Chart.lock (committed)
   helm lint charts/<app>
   tmp="$(mktemp -d)"; cp -r "charts/<app>" "$tmp/"; helm dependency build "$tmp/<app>"
   helm template <app> "$tmp/<app>" -n <app-namespace> >/dev/null; rm -rf "$tmp"
   ```
   All must pass; fix and re-run within the 3-attempt cap.
6. Deploy wiring: read from `.claude/CLAUDE.md` `GITOPS_REPO_URL` (the "GitOps repo
   URL" line), `ARGOCD_NAMESPACE` ("Argo CD namespace"), `DEST_SERVER` ("Destination
   cluster for <env>") and the default branch ("Default branch"), then render (use
   the dev/prod `targetRevision` rule from `argocd-repo-conventions` for
   `TARGET_REVISION`; `<app-namespace>` is the destination namespace):
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py" "${CLAUDE_PLUGIN_ROOT}/templates/application.yaml.tmpl" environments/<env>/apps/<app>.yaml \
     APP_NAME=<app> ENV_NAME=<env> NAMESPACE=<app-namespace> ARGOCD_NAMESPACE=<argocd-namespace> \
     GITOPS_REPO_URL=<gitops-repo-url> TARGET_REVISION=<rev> DEST_SERVER=<server>
   ```
   Create `environments/<env>/values/<app>.yaml` (comment-only).
7. Verify manifest by parsing it:
   `python -c "import sys,yaml; list(yaml.safe_load_all(open(sys.argv[1])))" environments/<env>/apps/<app>.yaml`.
8. Update `.claude/CLAUDE.md`: catalog inventory row + deployment matrix cell.
9. Commit in logical chunks (catalog, deploy wiring, docs), each with the
   `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer.
10. **Push/PR checkpoint.** Show the rendered file(s) and the drafted PR title + body. Unless the caller has already
    approved pushing (never assumed for a `prod`/`production` env), stop here and return the draft. On approval: push;
    `gh pr create` titled `Onboard <app> → <env>` with a body covering: chart + version + why, the
    `helm template ... | head -80` preview, target revision (+ prod pin caveat), destination namespace, and post-merge note
    ("the <env> root app syncs this automatically").
11. **Merge checkpoint, then drive it to healthy.** Unless the caller said `--yes` / "go ahead and merge", stop and
    return the PR with the next command. If merging: merge it, then load the `argocd-rollout` skill and run its loop
    (declared → Synced → Healthy → a passing functional check), obeying the caps in `argocd-sync` and the rollout skill;
    any fix goes through a further PR behind its own checkpoint.
12. Print the Hand-off section below.

## Failure handling

If any verification step fails and you cannot fix it in at most 3 attempts, stop.
Report what failed, the exact command and output, and your best hypothesis. Do
not open a PR for a chart that does not lint or template cleanly.

## Hand-off (always print this, filled in)

- **Done:** chart <name> <version>; PR <url or "not opened: <reason>">; files changed.
- **NOT done:** not merged / not synced / not verified on a cluster (say which).
- **Questions answered with defaults:** <list>.
- **Next command:** `git push -u origin onboard/<app>-<env> && gh pr create …` (if unpushed), else `/argocd-sync <app> <env>`.
