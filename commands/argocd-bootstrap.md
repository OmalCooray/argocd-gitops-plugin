---
name: argocd-bootstrap
description: Generate or refresh bootstrap/install.sh for a GitOps repo — the one-time script that installs Argo CD on a cluster and applies the environment's root application.
argument-hint: "[kube-context]"
---

You are generating `bootstrap/install.sh` for the Argo CD GitOps repo in the
current working directory.

## Preconditions

- CWD is a GitOps repo created by `/argocd-init-repo` (has `environments/<env>/`
  and `.claude/CLAUDE.md`). If not, tell the user to run `/argocd-init-repo` first.
- Read `.claude/CLAUDE.md` for: Argo CD namespace, environment name(s), GitOps
  repo URL, destination server.

## Steps

1. Load the skill `argocd-repo-conventions`.
2. Determine the Argo CD Helm chart version to pin:
   - Run `helm repo add argo https://argoproj.github.io/argo-helm` then
     `helm search repo argo/argo-cd --versions | head -5`.
   - If `helm` is unavailable, query ArtifactHub
     (`/packages/helm/argo/argo-cd`) via WebFetch.
   - Pick the latest stable. Record it.
3. If the repo has more than one environment, ask the user which environment this
   bootstrap targets (default: the only one, or the one the `$ARGUMENTS`
   kube-context maps to). `$ARGUMENTS` holds an optional kube-context.
4. Render `${CLAUDE_PLUGIN_ROOT}/templates/install.sh.tmpl` with these variables:
   `ARGOCD_NAMESPACE`, `ARGOCD_CHART_VERSION`, `ENV_NAME`, `GITOPS_REPO_URL`.
5. Write it to `bootstrap/install.sh`, `chmod +x` it.
6. Show the user the rendered script and the exact command to run:
   `./bootstrap/install.sh [kube-context]`.
7. Do **not** run it yourself — installing Argo CD onto a cluster is the user's
   call. Offer to run it if they confirm a context.

## Output

Print: the chart version pinned, the path written, and the run command. If
`$ARGUMENTS` gave a context, include it in the example.
