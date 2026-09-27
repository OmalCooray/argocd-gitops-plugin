---
name: argocd-review-values
description: Review a catalog app's values against the dev-ready or prod-ready rubric and report findings; optionally write a hardened per-environment overlay and open a PR. Read-only against the cluster.
argument-hint: "<app-name> [environment-name] [--profile dev|prod] [--write] [--context <name>]"
---

Review the effective Helm values for `<app>` and report how close they are to the
requested readiness profile.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each step, show commands + key output, checkpoint before `git push` /
opening the PR (only with `--write`), end with the findings table and verdict.

## Inputs

- `$1` — app name; `charts/<app>/` must exist.
- `$2` — environment name (optional). If given, the review merges
  `environments/<env>/values/<app>.yaml` on top of the base values.
- `--profile dev|prod` — which rubric (default: `prod`).
- `--write` — also write the recommended settings into
  `environments/<env>/values/<app>.yaml` and open a PR. Requires `$2`.

## Preconditions

0. **Resolve the target:** follow `${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`; use its `CTX` and `ARGOCD_NS` in every command below. Accept an optional `--context <name>` argument.
- CWD is a GitOps repo (`charts/<app>/Chart.yaml` exists; wrapper or own-app chart).
- `helm` available. No cluster required.

## Steps

1. Load skills `values-review` and `argocd-repo-conventions`.
2. Read `charts/<app>/Chart.yaml`. If it has **no `dependencies`**, it is an
   **own-app chart**: skip the upstream lookup (step 3), review
   `charts/<app>/values.yaml` + `templates/` directly, and remember its keys are
   **top-level** (no dependency-name nesting). Say so in the report. Otherwise it is a
   wrapper chart: take the upstream chart name, version and repo from `dependencies[0]`;
   its keys nest under `dependencies[0].name`.
3. Wrapper charts only: pull upstream defaults for reference:
   `helm show values <chart> --repo <repo-url> --version <version>` (or the
   `oci://` form). For a private/OCI chart see `helm-chart-onboarding`.
4. Render the effective manifests in a **temp copy** so the user's tree
   (`Chart.lock`, `charts/<app>/charts/`) is never rewritten. Use release name =
   `<app>` and `-n <dest-ns>` (the Application's destination namespace, from
   `apps/<app>.yaml` or the env's `argocd/` definition), otherwise resource names
   render as `release-name-<app>` and will not match the live objects or any
   `labelSelector` you write. A pre-existing `charts/<app>/charts/` (vendored, git-ignored)
   is overwritten in the temp copy only:
   ```bash
   tmp="$(mktemp -d)"; cp -r "charts/<app>" "$tmp/"; helm dependency build "$tmp/<app>"
   helm template <app> "$tmp/<app>" -n <dest-ns>      $( [ -n "$2" ] && echo -f "environments/$2/values/<app>.yaml" )      --api-versions policy/v1/PodDisruptionBudget      > "$tmp/rendered.yaml"
   ```
   Review `"$tmp/rendered.yaml"`; delete the temp dir (`rm -rf "$tmp"`) once the
   review (and, with `--write`, the verification render) is done. An own-app chart has
   no dependencies, so `helm dependency build` is a no-op for it.
   Optional and read-only: if a cluster is reachable and the target is resolved, compare
   the findings with live state (`kubectl --context "$CTX" get deploy <app> -n <dest-ns> -o yaml`:
   replicas, resources, probes). Never mutate.
5. Apply the `values-review` checklist for `--profile`. Produce the findings
   table: `severity | area | finding | fix (values key → suggested value)`,
   blockers first. A PodDisruptionBudget usually renders only when `replicaCount > 1`,
   so recommend replica and PDB changes together. Findings that need a template change
   (no PDB template, no HPA, no anti-affinity template) are reported as
   "needs a chart change, not a values change" and are NOT written to any overlay.
6. Print a one-line verdict: `<app> @ <profile>: <n> blockers, <m> warnings`.
7. If `--write`:
   1. Require a clean tree: `git status --porcelain` must be empty, otherwise stop and ask.
   2. `git switch -c review/<app>-<env>-<profile>`.
   3. Merge the recommended values keys into `environments/<env>/values/<app>.yaml`.
      Wrapper chart: nest under the dependency name. Own-app chart: **top-level** keys, no
      nesting. Never touch the base `charts/<app>/values.yaml` for env-specific values.
      Keep existing keys; only add/adjust.
   4. Do **not** invent secret values: for anything secret, write the
      `existingSecret` / `*SecretName` reference and list the Secrets the user
      must create separately.
   5. **No-op rule:** if the rubric yields no values change for the chosen profile
      (`git diff --quiet -- "environments/<env>/values/<app>.yaml"` succeeds, i.e. the
      overlay is unchanged), print `nothing to harden for profile <profile>` with a one-line
      list of what was checked, switch back, delete the empty, unpushed branch
      (`git branch -D review/<app>-<env>-<profile>`), and stop. Do not commit.
   6. Re-render in a temp copy (step 4 commands) and confirm `helm template <app> ... -n <dest-ns>`
      still succeeds and the changed keys show up in the render (e.g. `grep -n 'replicas:'`).
   7. `git add environments/<env>/values/<app>.yaml`, then `git commit`.
   8. **Checkpoint:** `> About to push review/<app>-<env>-<profile> and open a PR. Proceed?`
   9. Push and open the PR titled `Harden <app> values for <env>`. Write the PR body
      yourself:
      - the findings table (severity blocker/warn/note, key path, current → proposed,
        one-line why);
      - a **verified by** line stating the temp-copy `helm template <app> ... -n <dest-ns>`
        result: it renders, and the changed keys appear in the render (cite one grep,
        e.g. `grep -n 'replicas:'`);
      - a checklist of Secrets/prerequisites the user must provide;
      - the "needs a chart change" findings, listed separately.
      Follow `${CLAUDE_PLUGIN_ROOT}/references/no-remote-fallback.md` when present;
      otherwise print the branch, PR body and the exact `git push -u origin <branch>` /
      `gh pr create ...` commands and stop with status `not pushed: <reason>`.

## Notes

- **Read-only against the cluster.** Never sync or apply. The output is advice
  plus, optionally, a PR.
- If a blocker needs a second app (e.g. an external database), say so explicitly
  and point at `/argocd-add-chart` + `/argocd-deploy`; do not scaffold it here.
