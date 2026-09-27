---
name: argocd-init-repo
description: Scaffold a new Argo CD GitOps repo (catalog + one environment + root app + bootstrap + CLAUDE.md + CODEOWNERS), commit it, and optionally create and push the GitHub repo.
argument-hint: "<repo-name> [environment-name]"
---

Create a new Argo CD GitOps repository skeleton.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each step, show commands + key output, checkpoint before `git push` /
creating the GitHub repo, end with a summary and the next command.

## Inputs

- `$1` — repo name (required), e.g. `data-platform-k8s-configs`.
- `$2` — first environment name (optional, default `default`). Kebab-case.
- Ask the user (AskUserQuestion) for anything not derivable:
  1. Target directory to create the repo in (default: a sibling of the CWD).
  2. GitHub owner/org — default from `gh api user --jq .login` (if `gh` is
     unauthenticated, ask for the owner — no default — and step 6 will print the
     manual commands).
  3. Argo CD namespace (default: `argocd`) — this is `<argocd-namespace>` below.
  4. Destination cluster API (default: `https://kubernetes.default.svc`) — this is `<server>` below.
  5. Default branch — default from `git config --get init.defaultBranch`, else `main`.
  6. Visibility (`private` | `public`; default `private`). **Private repos need
     Argo CD credentials — `/argocd-bootstrap` sets them up with a read-only deploy
     key.** Public repos are pulled anonymously.
  7. Create + push the GitHub repo now? (yes/no; needs `gh` authenticated.)

## Steps

0. If the target directory exists and is non-empty (or already a git repo), stop
   and ask the user how to proceed — never overwrite.
1. Load skill `argocd-repo-conventions`.
2. Create the directory tree:
   ```
   <name>/
     charts/.gitkeep
     environments/<env>/apps/.gitkeep
     environments/<env>/values/.gitkeep
     environments/<env>/root.yaml
     bootstrap/.gitkeep
     .claude/CLAUDE.md
     CODEOWNERS
     README.md
     .gitignore
     .gitattributes
   ```
3. Render each template with the renderer script (it fails on a missing or unused
   variable, and writes UTF-8 with LF newlines). Values:
   - `<argocd-namespace>` = input 3 (Argo CD namespace); `<server>` = input 4
     (destination cluster API); `<branch>` = input 5; `<owner>` = input 2.
   - `<gitops-repo-url>` = `https://github.com/<owner>/<name>` for a `public` repo and
     `git@github.com:<owner>/<name>.git` for a `private` repo (deploy-key access needs
     the SSH form).
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py" "${CLAUDE_PLUGIN_ROOT}/templates/root.yaml.tmpl" environments/<env>/root.yaml \
     ENV_NAME=<env> ARGOCD_NAMESPACE=<argocd-namespace> GITOPS_REPO_URL=<gitops-repo-url> DEFAULT_BRANCH=<branch> DEST_SERVER=<server>
   python "${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py" "${CLAUDE_PLUGIN_ROOT}/templates/gitops-README.md.tmpl" README.md GITOPS_REPO_NAME=<name>
   python "${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py" "${CLAUDE_PLUGIN_ROOT}/templates/gitops-CLAUDE.md.tmpl" .claude/CLAUDE.md \
     ENV_NAME=<env> ARGOCD_NAMESPACE=<argocd-namespace> GITOPS_REPO_URL=<gitops-repo-url> DEFAULT_BRANCH=<branch> DEST_SERVER=<server>
   python "${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py" "${CLAUDE_PLUGIN_ROOT}/templates/CODEOWNERS.tmpl" CODEOWNERS ENV_NAME=<env> GITHUB_OWNER=<owner>
   ```
   (`bootstrap/install.sh` is rendered later by `/argocd-bootstrap`.)
4. `.gitignore` content:
   ```
   charts/*/charts/
   charts/*/*.tgz
   ```
   `.gitattributes` content: `* text=auto eol=lf` and `*.sh text eol=lf`.
5. `git init -b <branch>`, `git add -A`,
   `git commit -m "chore: scaffold GitOps repo"` (add the Co-Authored-By trailer).
6. If the user said yes to GitHub:
   - If `VISIBILITY` is `public`, print `This repository will be PUBLIC`.
   - Checkpoint (both visibilities):
     `> About to create <private|PUBLIC> repo <owner>/<name> and push <branch>. Proceed?`
   - `gh repo create <owner>/<name> --$VISIBILITY --source . --remote origin --push`
     (`$VISIBILITY` is `private` or `public`).
   - `git remote set-url origin <gitops-repo-url>` so `origin` matches the URL recorded
     in the repo (SSH for private, https for public); later `git ls-remote` / pushes
     then use the same URL Argo CD does.
   - If `gh` is missing or unauthenticated, print the manual commands and stop:
     `gh repo create <owner>/<name> --<visibility> --source . --remote origin --push`,
     or, with an empty repo created in the GitHub UI,
     `git remote add origin <gitops-repo-url> && git push -u origin <branch>`.
7. Print next steps: `/argocd-bootstrap`, then `/argocd-add-chart`, then
   `/argocd-deploy`.

## Notes

- Never force-push. Never create the repo public unless the user explicitly chose `public`.
- Creating the GitHub repo is a side-effecting action — only after explicit yes.
