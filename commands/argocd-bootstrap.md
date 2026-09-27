---
name: argocd-bootstrap
description: Generate or refresh bootstrap/install.sh for a GitOps repo — the one-time script that installs Argo CD on a cluster and applies the environment's root application.
argument-hint: "[kube-context | --context <name>] [--env <environment>]"
---

You are generating `bootstrap/install.sh` for the Argo CD GitOps repo in the
current working directory.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each step, show commands and their key output, run the install in the
foreground with visible progress, checkpoint before touching the cluster, no
silent background jobs or polling loops.

## Preconditions

0. **Resolve the target:** follow `${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`; use its `CTX` and `ARGOCD_NS` in every command below. Accept an optional `--context <name>` argument. `$1` is a kube-context (or `--context <name>`); the environment is chosen with `--env <name>` (default: the repo's only environment, else ask).
- CWD is a GitOps repo created by `/argocd-init-repo` (has `environments/<env>/`
  and `.claude/CLAUDE.md`). If not, tell the user to run `/argocd-init-repo` first.
- Read `.claude/CLAUDE.md` for: Argo CD namespace, environment name(s), GitOps
  repo URL, destination server.

## Steps

1. Load the skill `argocd-repo-conventions`.
2. Determine the Argo CD Helm chart version to pin (local only, no cluster):
   - Run `helm repo add argo https://argoproj.github.io/argo-helm` then pick the
     version without `jq` (use `python3` if `python` is missing):
     ```bash
     helm search repo argo/argo-cd --versions -o json --max-col-width 0 | python -c "import json,sys; print(next(e['version'] for e in json.load(sys.stdin) if '-' not in e['version'] and '-' not in e['app_version']))"
     ```
   - That is the first entry whose chart `version` and `app_version` both have no
     `-` pre-release suffix; record it in `install.sh`.
   - If `helm` is unavailable, query ArtifactHub
     (`/packages/helm/argo/argo-cd`) via WebFetch and pick the latest stable.
3. If the repo has more than one environment, ask the user which environment this
   bootstrap targets, unless `--env <name>` was given (default: the only one). `$ARGUMENTS` holds an optional kube-context, given positionally or as `--context <name>` (both mean the same thing); it is never the environment.
4. Render `${CLAUDE_PLUGIN_ROOT}/templates/install.sh.tmpl` with the renderer script,
   reading the values from `.claude/CLAUDE.md` (labels `Argo CD namespace`,
   `GitOps repo URL`; the environment from step 3; the chart version from step 2):
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py" "${CLAUDE_PLUGIN_ROOT}/templates/install.sh.tmpl" bootstrap/install.sh ARGOCD_NAMESPACE="$ARGOCD_NS" ARGOCD_CHART_VERSION=<chart-version> ENV_NAME=<env> GITOPS_REPO_URL=<repo-url>
   ```
5. Show the rendered script. Work on a branch and commit it, marking it
   executable in git (Windows records mode 100644 otherwise):
   ```bash
   git switch -c bootstrap/install-<env>
   git add bootstrap/install.sh
   git update-index --chmod=+x bootstrap/install.sh
   git commit -m "chore(bootstrap): pin Argo CD chart and render install.sh"
   ```
   (Add the Co-Authored-By trailer.) There is ONE `bootstrap/install.sh` per repo: bootstrapping another environment re-renders it for that environment (only `ENV_NAME` and the header comment change), so commit it on the same `bootstrap/install-<env>` branch flow and expect that diff. Nothing is pushed yet; the push/PR happens once,
   in step 10.
6. **Checkpoint:** `> Run ./bootstrap/install.sh against context "$CTX" now? It
   installs Argo CD (~3 min) and applies the root app.` Wait for yes.
7. On yes, run `./bootstrap/install.sh "$CTX"` **in the foreground** so its output (helm progress, CRD wait,
   root-app apply) streams into the conversation. Do not background it.
   `install.sh` printed how to open the UI and get the admin password; repeat
   those lines if the output scrolled. For a private repo the root app was applied
   before Argo CD had a credential, so `root-<env>` showing a ComparisonError
   `failed to list refs: error creating SSH agent: "SSH agent requested but SSH_AUTH_SOCK not-specified"` (ssh URL, no credential yet) or
   `authentication required: Repository not found` (https URL on a private repo): either of these (Sync status Unknown) on `root-<env>` right after `install.sh` is expected until the credential exists; step 8 fixes it.
   The credential step runs after `install.sh` because the Argo CD namespace and CRDs do not exist before it, so a brief Unknown state on the root is normal. On no, just
   print the command for them to run later and skip steps 8-9.
8. **Private-repo access** (only after `install.sh` finished).
   - Derive `OWNER` and `NAME` from the recorded `GitOps repo URL`: strip a trailing
     `.git` and the `git@github.com:` or `https://github.com/` prefix, then set
     `OWNER=<owner> NAME=<name>` shell variables and use `"$OWNER"`/`"$NAME"` below.
   - Preconditions: `gh` (authenticated) and `ssh-keygen` (OpenSSH) are needed for
     private repos only. If either is missing, print the manual fallback and stop:
     run `ssh-keygen -t ed25519 -N "" -f <keyfile>`; paste `<keyfile>.pub` into the
     repo's Settings -> Deploy keys (leave "Allow write access" unticked); then run
     the two `kubectl` commands from the block below with `--from-file=sshPrivateKey=<keyfile>`,
     and delete the key files.
   - Detect visibility: `gh repo view "$OWNER/$NAME" --json visibility -q .visibility`.
     `PRIVATE` and `INTERNAL` count as private; `PUBLIC` skips to step 9. If `gh`
     cannot answer, probe anonymously:
     `GIT_TERMINAL_PROMPT=0 git ls-remote https://github.com/"$OWNER"/"$NAME".git HEAD`.
     Only an authentication failure (exit 128 with "Authentication failed",
     "could not read Username" or "not found") means private; a network error means
     unknown, so ask the user.
   - If Secret `repo-$NAME` already exists
     (`kubectl --context "$CTX" -n "$ARGOCD_NS" get secret "repo-$NAME" --ignore-not-found`),
     say that a Secret named `repo-$NAME` already exists for this repo in this cluster, so no new deploy key is created, and skip the credential creation (idempotent re-run). Verify it points at the recorded URL by printing ONLY the url value:
     `kubectl --context "$CTX" -n "$ARGOCD_NS" get secret "repo-$NAME" -o jsonpath='{.data.url}' | base64 -d`
     (the url is not sensitive, the key is; NEVER read `.data.sshPrivateKey`). If it differs from the recorded `GITOPS_REPO_URL`, stop and tell the user; do not overwrite silently. Otherwise still do the
     https-to-ssh check below.
   - The recorded URL must be the SSH form `git@github.com:$OWNER/$NAME.git`. If it is
     https, the Secret (keyed to the SSH URL) would never match. Propose this exact
     edit under ONE checkpoint: every `repoURL:` whose value is
     `https://github.com/$OWNER/$NAME` (with or without `.git`) becomes
     `git@github.com:$OWNER/$NAME.git` in `environments/*/root.yaml` and in every
     `environments/*/apps/*.yaml` (both sources of each app: the chart-path source and
     the `ref: values` source), plus the `GitOps repo URL` line in `.claude/CLAUDE.md`.
     Then re-render `bootstrap/install.sh` with the renderer (step 4) using the new
     `GITOPS_REPO_URL` so its header comment is not stale, and commit on the
     `bootstrap/install-<env>` branch. Because the root cannot read git yet, a merged
     branch alone cannot fix the live root, so apply it from the working tree:
     `kubectl --context "$CTX" apply -n "$ARGOCD_NS" -f environments/<env>/root.yaml`.
     Tell the user the child apps stay on https in git until the PR (step 10) is merged.
   - **Checkpoint:** `> This repo is private. About to add a READ-ONLY deploy key to <owner>/<name> on GitHub and create Secret repo-<name> in "$CTX" (namespace "$ARGOCD_NS"); the private key is deleted locally. Proceed?`
   - On yes (never print, cat or log the private key or Secret data; the deploy key is added read-only, gh's default):
     ```bash
     KEY="$(mktemp -d)/argocd-deploy-key"
     ssh-keygen -t ed25519 -N "" -C "argocd-$NAME" -f "$KEY"
     gh repo deploy-key add "$KEY.pub" --title "argocd-readonly-$CTX" -R "$OWNER/$NAME"
     kubectl --context "$CTX" -n "$ARGOCD_NS" create secret generic "repo-$NAME" --from-literal=type=git --from-literal=url="git@github.com:$OWNER/$NAME.git" --from-file=sshPrivateKey="$KEY"
     kubectl --context "$CTX" -n "$ARGOCD_NS" label secret "repo-$NAME" argocd.argoproj.io/secret-type=repository
     shred -u "$KEY" 2>/dev/null || rm -f "$KEY"; rm -f "$KEY.pub"; rmdir "$(dirname "$KEY")"
     ```
   - Verify the key is read-only: `gh repo deploy-key list -R "$OWNER/$NAME" --json title,read_only` shows `read_only: true` for the new title.
   - On ANY failure after `ssh-keygen`: delete `$KEY*` and its temp dir, report the ONE
     error line, and stop. If the GitHub key was already added but the Secret creation
     failed, name the key title `argocd-readonly-<ctx>` to remove in the repo's
     Settings -> Deploy keys.
   - Each run creates a NEW deploy key (titles may repeat; GitHub only rejects a
     duplicate key). Old keys are not revoked automatically: list them with
     `gh repo deploy-key list -R "$OWNER/$NAME"` and remove with `gh repo deploy-key delete`.
     The local private key is safe to delete because only the cluster Secret needs it.
     To rotate, delete the Secret and run this step again.
   - Argo CD ships GitHub's SSH host keys, so github.com needs no `known_hosts`
     step; for other hosts the user must add theirs (out of scope).
   - Refresh the root (a refresh starts no operation):
     `kubectl --context "$CTX" -n "$ARGOCD_NS" annotate application root-<env> argocd.argoproj.io/refresh=hard --overwrite`
     Allow ONE bounded re-check about 15 s later (no loop). If `root-<env>` is still not
     Synced, run once
     `kubectl --context "$CTX" -n "$ARGOCD_NS" get application root-<env> -o jsonpath='{.status.conditions[*].message}'`,
     report that single line, and hand back with the likely causes: deploy key not
     added, the org disallows deploy keys, or a URL mismatch.
9. FINAL-CHECK: run `kubectl --context "$CTX" get applications -n "$ARGOCD_NS"` once and show the
   result; `root-<env>` should reach Synced.
10. **Checkpoint** before `git push` + PR for the `bootstrap/install-<env>` branch (show
    branch name and PR title). Follow
    `${CLAUDE_PLUGIN_ROOT}/references/no-remote-fallback.md` for the no-remote / no-`gh` cases.

## Output

A short summary: chart version pinned, `bootstrap/install.sh` written, whether
the install ran and what Argo CD reports, and the next command
(`/argocd-add-chart`).
