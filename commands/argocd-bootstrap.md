---
name: argocd-bootstrap
description: Generate or refresh bootstrap/install.sh for a GitOps repo — the one-time script that installs Argo CD on a cluster and applies the environment's root application.
argument-hint: "[kube-context | --context <name>]"
---

You are generating `bootstrap/install.sh` for the Argo CD GitOps repo in the
current working directory.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each step, show commands and their key output, run the install in the
foreground with visible progress, checkpoint before touching the cluster, no
silent background jobs or polling loops.

## Preconditions

0. **Resolve the target:** follow `${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`; use its `CTX` and `ARGOCD_NS` in every command below. Accept an optional `--context <name>` argument.
- CWD is a GitOps repo created by `/argocd-init-repo` (has `environments/<env>/`
  and `.claude/CLAUDE.md`). If not, tell the user to run `/argocd-init-repo` first.
- Read `.claude/CLAUDE.md` for: Argo CD namespace, environment name(s), GitOps
  repo URL, destination server.

## Steps

1. Load the skill `argocd-repo-conventions`.
2. Determine the Argo CD Helm chart version to pin (local only, no cluster):
   - Run `helm repo add argo https://argoproj.github.io/argo-helm` then
     `helm search repo argo/argo-cd --versions -o json --max-col-width 0`.
   - Take the first entry whose `version` has no `-` pre-release suffix; record
     its chart `version` in `install.sh`.
   - If `helm` is unavailable, query ArtifactHub
     (`/packages/helm/argo/argo-cd`) via WebFetch and pick the latest stable.
3. If the repo has more than one environment, ask the user which environment this
   bootstrap targets (default: the only one, or the one the `$ARGUMENTS`
   kube-context maps to). `$ARGUMENTS` holds an optional kube-context, given positionally or as `--context <name>` (both mean the same thing).
4. Render `${CLAUDE_PLUGIN_ROOT}/templates/install.sh.tmpl` with the renderer script,
   reading the values from `.claude/CLAUDE.md` (labels `Argo CD namespace`,
   `GitOps repo URL`; the environment from step 3; the chart version from step 2):
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py" "${CLAUDE_PLUGIN_ROOT}/templates/install.sh.tmpl" bootstrap/install.sh ARGOCD_NAMESPACE="$ARGOCD_NS" ARGOCD_CHART_VERSION=<chart-version> ENV_NAME=<env> GITOPS_REPO_URL=<repo-url>
   ```
5. Show the rendered script. Commit it and mark it executable in git (Windows
   records mode 100644 otherwise):
   ```bash
   git add bootstrap/install.sh
   git update-index --chmod=+x bootstrap/install.sh
   ```
6. **Checkpoint:** `> Run ./bootstrap/install.sh against context "$CTX" now? It
   installs Argo CD (~3 min) and applies the root app.` Wait for yes.
7. On yes, run `./bootstrap/install.sh "$CTX"` **in the foreground** so its output (helm progress, CRD wait,
   root-app apply) streams into the conversation. Do not background it.
   `install.sh` printed how to open the UI and get the admin password; repeat
   those lines if the output scrolled. On no, just print the command for them to
   run later and skip steps 8-9.
8. **Private-repo access** (only after `install.sh` finished). Let `<owner>/<name>`
   come from the recorded `GitOps repo URL`. Precondition: `ssh-keygen` (OpenSSH) is
   needed for private repos only; if it is missing, print the manual steps below
   and stop.
   - Detect visibility: `gh repo view <owner>/<name> --json visibility -q .visibility`.
     If `gh` is unavailable, probe anonymously:
     `GIT_TERMINAL_PROMPT=0 git ls-remote https://github.com/<owner>/<name>.git HEAD`
     (failure means treat it as private). Public: skip to step 9.
   - Private: the recorded URL must be the SSH form `git@github.com:<owner>/<name>.git`.
     If it is https, **checkpoint** and, on yes, edit `environments/<env>/root.yaml`,
     `.claude/CLAUDE.md` and every `environments/*/apps/*.yaml` `repoURL` equal to the
     old URL to the SSH form on a branch. Never rewrite silently.
   - If Secret `repo-<name>` already exists
     (`kubectl --context "$CTX" -n "$ARGOCD_NS" get secret repo-<name>`), say so and
     skip the rest of this step (idempotent re-run).
   - **Checkpoint:** `> This repo is private: Argo CD needs a read-only deploy key. Create one (the private key is stored only in a cluster Secret and deleted locally)? Proceed?`
   - On yes (never print, cat or log the private key or Secret data; the deploy key is added read-only, gh's default):
     ```bash
     KEY="$(mktemp -d)/argocd-deploy-key"
     ssh-keygen -t ed25519 -N "" -C "argocd-<name>" -f "$KEY"
     gh repo deploy-key add "$KEY.pub" --title "argocd-readonly-$CTX" -R <owner>/<name>
     kubectl --context "$CTX" -n "$ARGOCD_NS" create secret generic repo-<name> --from-literal=type=git --from-literal=url=git@github.com:<owner>/<name>.git --from-file=sshPrivateKey="$KEY"
     kubectl --context "$CTX" -n "$ARGOCD_NS" label secret repo-<name> argocd.argoproj.io/secret-type=repository
     shred -u "$KEY" 2>/dev/null || rm -f "$KEY"; rm -f "$KEY.pub"
     ```
   - Argo CD ships GitHub's SSH host keys, so github.com needs no `known_hosts`
     step; for other hosts the user must add theirs (out of scope).
   - `install.sh` applied the root app before the credential existed, so refresh it
     (a refresh starts no operation):
     `kubectl --context "$CTX" -n "$ARGOCD_NS" annotate application root-<env> argocd.argoproj.io/refresh=hard --overwrite`
9. Run `kubectl --context "$CTX" get applications -n "$ARGOCD_NS"` once and show the
   result; `root-<env>` should reach Synced (re-check once after a private-repo refresh).

## Output

A short summary: chart version pinned, `bootstrap/install.sh` written, whether
the install ran and what Argo CD reports, and the next command
(`/argocd-add-chart`).
