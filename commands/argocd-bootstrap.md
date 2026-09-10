---
name: argocd-bootstrap
description: Generate or refresh bootstrap/install.sh for a GitOps repo — the one-time script that installs Argo CD on a cluster and applies the environment's root application.
argument-hint: "[kube-context]"
---

You are generating `bootstrap/install.sh` for the Argo CD GitOps repo in the
current working directory.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each step, show commands and their key output, run the install in the
foreground with visible progress, checkpoint before touching the cluster, no
silent background jobs or polling loops.

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
5. Write it to `bootstrap/install.sh`, `chmod +x` it. Show the rendered script.
6. **Checkpoint:** `> Run ./bootstrap/install.sh against context <ctx> now? It
   installs Argo CD (~3 min) and applies the root app.` Wait for yes.
7. On yes, run it **in the foreground** so its output (helm progress, CRD wait,
   root-app apply) streams into the conversation. Do not background it. When it
   returns, run `kubectl get applications -n <argocd-ns>` once and show the
   result. On no, just print the command for them to run later.

## Output

A short summary: chart version pinned, `bootstrap/install.sh` written, whether
the install ran and what Argo CD reports, and the next command
(`/argocd-add-chart`).
