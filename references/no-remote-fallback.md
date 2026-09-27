# No remote / no `gh`

Shared by every command and agent that pushes a branch or opens a PR. Follow it at the push step.

## Checks (read-only, run before any `git push` or `gh pr create`)

```bash
git remote get-url origin     # is there a remote, and which URL?
gh auth status                # is `gh` installed and logged in?
```

## Cases

- **No `origin` remote.** Never push, and never push to a remote the user did not configure (do not invent or add
  one). Keep all commits on the local branch. Print the branch name, the drafted PR title and body, and the commands
  to run once a remote exists (`git remote add origin <url> && git push -u origin <branch>`, then `gh pr create ...`).
  Stop with status `not pushed: no remote`.
- **`gh` missing or not logged in.** If `origin` exists and the user confirmed the push, push the branch. Do not open
  the PR: print the PR title and body plus the compare URL
  `<repo-url>/compare/<default-branch>...<branch>?expand=1`, and tell the user to open the PR in the browser.
  Report `PR: not opened — gh not installed` (or `— gh not authenticated`). If the push itself cannot run, stop with
  `not pushed: <reason>`.
- **Nothing to push** (the branch has no commits ahead of the default branch). Say so and delete the empty branch.

## Notes

- `origin` may be an SSH URL (`git@github.com:<owner>/<repo>.git`), which is the norm for private repos. The Argo CD
  deploy key is read-only and belongs to Argo CD: it is NOT a push credential. Pushing needs the user's own
  credentials (their SSH key or a logged-in `gh`); if the push is rejected for auth, report
  `not pushed: authentication failed` and leave the commits local.
- Status strings used elsewhere: `not pushed: <reason>` (hand-offs, final summaries) and
  `PR: not opened — <reason>` (onboarder hand-off, PR line).
- Read-only against the user's setup: do not run `gh auth login` or change git configuration on the user's behalf.
