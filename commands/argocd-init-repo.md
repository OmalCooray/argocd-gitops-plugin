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
  2. GitHub owner/org (default: `OmalCooray`).
  3. Argo CD namespace (default: `argocd`).
  4. Destination cluster API (default: `https://kubernetes.default.svc`).
  5. Default branch name (default: `master`).
  6. Create + push the GitHub repo now? (yes/no; needs `gh` authenticated.)

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
3. Render from `${CLAUDE_PLUGIN_ROOT}/templates/`:
   - `root.yaml.tmpl` → `environments/<env>/root.yaml`
     (vars: `ENV_NAME`, `ARGOCD_NAMESPACE`, `GITOPS_REPO_URL`, `DEFAULT_BRANCH`,
     `DEST_SERVER`). `GITOPS_REPO_URL` = `https://github.com/<owner>/<name>`.
   - `gitops-README.md.tmpl` → `README.md` (vars: `GITOPS_REPO_NAME`, `ENV_NAME`).
   - `gitops-CLAUDE.md.tmpl` → `.claude/CLAUDE.md` (all repo-fact vars; note it
     needs `DEFAULT_BRANCH` — the branch name — not `TARGET_REVISION`).
   - `CODEOWNERS.tmpl` → `CODEOWNERS` (vars: `ENV_NAME`, `GITHUB_OWNER` — the
     owner/org from input 2).

   `DEFAULT_BRANCH` is the branch name from input 5 (default `master`).
4. `.gitignore` content:
   ```
   charts/*/charts/
   charts/*/*.tgz
   ```
   `.gitattributes` content: `* text=auto eol=lf` and `*.sh text eol=lf`.
5. `git init -b <branch>`, `git add -A`,
   `git commit -m "chore: scaffold GitOps repo"` (add the Co-Authored-By trailer).
6. If the user said yes to GitHub:
   - `gh repo create <owner>/<name> --private --source . --remote origin --push`
   - If `gh` is missing or unauthenticated, print the manual commands and stop.
7. Print next steps: `/argocd-bootstrap`, then `/argocd-add-chart`, then
   `/argocd-deploy`.

## Notes

- Never force-push. Never create the repo public unless the user explicitly asks.
- Creating the GitHub repo is a side-effecting action — only after explicit yes.
