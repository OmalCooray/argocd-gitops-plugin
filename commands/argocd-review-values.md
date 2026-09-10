---
name: argocd-review-values
description: Review a catalog app's values against the dev-ready or prod-ready rubric and report findings; optionally write a hardened per-environment overlay and open a PR. Read-only against the cluster.
argument-hint: "<app-name> [environment-name] [--profile dev|prod] [--write]"
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

- CWD is a GitOps repo (`charts/<app>/Chart.yaml` exists).
- `helm` available. No cluster required.

## Steps

1. Load skills `values-review` and `argocd-repo-conventions`.
2. Read `charts/<app>/Chart.yaml` for the upstream chart name, version, repo.
3. Pull upstream defaults for reference:
   `helm show values <chart> --repo <repo-url> --version <version>` (or the
   `oci://` form). For a private/OCI chart see `helm-chart-onboarding`.
4. Render the effective manifests:
   ```bash
   helm dependency build charts/<app>
   helm template charts/<app> \
     $( [ -n "$2" ] && echo -f environments/$2/values/<app>.yaml ) \
     --api-versions policy/v1/PodDisruptionBudget \
     > /tmp/<app>-rendered.yaml
   ```
5. Apply the `values-review` checklist for `--profile`. Produce the findings
   table: `severity | area | finding | fix (values key → suggested value)`,
   blockers first.
6. Print a one-line verdict: `<app> @ <profile>: <n> blockers, <m> warnings`.
7. If `--write`:
   - `git switch -c harden/<app>-<env>`.
   - Merge the recommended keys into `environments/<env>/values/<app>.yaml`
     (nested under the subchart name; never touch the base `charts/<app>/values.yaml`
     for env-specific values). Keep existing keys; only add/adjust.
   - Do **not** invent secret values — for anything secret, write the
     `existingSecret` / `*SecretName` reference and list the Secrets the user
     must create separately.
   - Re-render with the new overlay and confirm `helm template` still succeeds.
   - Commit. Push. `gh pr create` titled `Harden <app> values for <env>` with the
     findings table in the body and a checklist of Secrets/prerequisites the user
     must provide. `gh` missing → print the branch + body, stop.

## Notes

- **Read-only against the cluster.** Never sync or apply. The output is advice
  plus, optionally, a PR.
- If a blocker needs a second app (e.g. an external database), say so explicitly
  and point at `/argocd-add-chart` + `/argocd-deploy`; do not scaffold it here.
