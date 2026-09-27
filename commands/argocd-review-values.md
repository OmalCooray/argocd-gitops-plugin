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

1. Load skills `values-review` and `argocd-repo-conventions`. Record the current branch
   (`git branch --show-current`) as `<orig-branch>`; a `--write` run returns to it on a no-op.
2. Read `charts/<app>/Chart.yaml`. If it has **no `dependencies`**, it is an
   **own-app chart**: skip the upstream lookup (step 3), review
   `charts/<app>/values.yaml` + `templates/` directly, and remember its keys are
   **top-level** (no dependency-name nesting). Say so in the report. Otherwise it is a
   wrapper chart: take the upstream chart name, version and repo from `dependencies[0]`.
   Its values key is `dependencies[0].alias` when the dependency has an `alias`, else
   `dependencies[0].name`; all wrapper keys nest under it. If there are several
   dependencies, report that and ask which one to review; do not guess.
3. Wrapper charts only: pull upstream defaults for reference:
   `helm show values <chart> --repo <repo-url> --version <version>` (or the
   `oci://` form). For a private/OCI chart see `helm-chart-onboarding`.
4. Render the effective manifests with the render script. It works on a **temp copy** (your
   `Chart.lock`, `charts/<app>/charts/` and Helm repo list are never touched; a vendored
   `charts/<app>/charts/` is overwritten in the copy only) and uses release name = `<app>` and
   `-n <dest-ns>` (the Application's destination namespace, from the env's
   `environments/<env>/apps/<app>.yaml`), otherwise names render as `release-name-<app>` and will not
   match the live objects or any `labelSelector` you write. Add the `--values` argument only when
   `$2` (an environment) was given:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/render_chart.sh" "charts/<app>" <app> <dest-ns>      --values "environments/<env>/values/<app>.yaml"      -- --api-versions policy/v1/PodDisruptionBudget > "$(mktemp -d)/rendered.yaml"
   ```
   Keep the printed temp path; review that file. If the script exits non-zero, show its `error:`
   line and stop.
   Optional and read-only: if a cluster is reachable and the target is resolved, compare
   the findings with live state. Only `.spec.replicas`, container `resources` and probes are
   read; never Secrets, never mutate:
   ```bash
   kubectl --context "$CTX" -n <dest-ns> get deploy <name> -o jsonpath='{.spec.replicas}'
   kubectl --context "$CTX" -n <dest-ns> get deploy <name> -o jsonpath='{.spec.template.spec.containers[*].resources}'
   kubectl --context "$CTX" -n <dest-ns> get sts <name> -o jsonpath='{.spec.template.spec.containers[*].readinessProbe}'
   ```
5. Apply the `values-review` checklist for `--profile`. Produce the findings
   table: `severity | area | finding | fix (values key → suggested value)`,
   blockers first. A PodDisruptionBudget usually renders only when `replicaCount > 1`,
   so recommend replica and PDB changes together. Findings that need a template change
   are reported as "needs a chart change, not a values change" and are NOT written to any
   overlay. To decide: list `charts/<app>/templates/` and check the render, e.g.
   `grep -c 'kind: PodDisruptionBudget' <rendered>` (0 with `replicaCount > 1` means there is no
   PDB template), and likewise `HorizontalPodAutoscaler` and `podAntiAffinity`.
6. Print a one-line verdict: `<app> @ <profile>: <n> blockers, <m> warnings`.
7. If `--write`:
   1. Require a clean tree: `git status --porcelain` must be empty, otherwise stop and ask.
   2. `git switch -c review/<app>-<env>-<profile>`.
   3. Merge the recommended values keys into `environments/<env>/values/<app>.yaml`.
      Wrapper chart: nest under the values key from step 2. Own-app chart: **top-level** keys, no
      nesting. Never touch the base `charts/<app>/values.yaml` for env-specific values.
      Keep existing keys; only add/adjust.
   4. Do **not** invent secret values: for anything secret, write the
      `existingSecret` / `*SecretName` reference and list the Secrets the user
      must create separately.
   5. **No-op rule:** if the rubric yields no values change for the chosen profile
      (`git status --porcelain -- environments/<env>/values/<app>.yaml` prints nothing; do not use
      `git diff`, which is silent for a new untracked overlay), print
      `nothing to harden for profile <profile>` with a one-line list of what was checked, remove any
      comment-only overlay you just created, `git switch <orig-branch>`, delete the empty, unpushed branch
      (`git branch -D review/<app>-<env>-<profile>`), and stop. Do not commit.
   6. Re-render with step 4's command (temp copy) and confirm it still succeeds and the changed
      keys show up in the render (e.g. pipe to `grep -n 'replicas:'`).
   7. `git add environments/<env>/values/<app>.yaml`, then `git commit`.
   8. **Checkpoint:** `> About to push review/<app>-<env>-<profile> and open a PR. Proceed?`
   9. Push and open the PR titled `Harden <app> values for <env>`. Write the PR body
      yourself:
      - the findings table (severity blocker/warn/note, key path, current → proposed,
        one-line why);
      - a **verified by** line stating the temp-copy render result
        (`render_chart.sh charts/<app> <app> <dest-ns> ...`): it renders, and the changed keys
        appear in the render (cite one grep, e.g. `grep -n 'replicas:'`);
      - a checklist of Secrets/prerequisites the user must provide;
      - the "needs a chart change" findings, listed separately.
      Follow `${CLAUDE_PLUGIN_ROOT}/references/no-remote-fallback.md`
      (status `not pushed: <reason>`).

## Notes

- **Read-only against the cluster.** Never sync or apply. The output is advice
  plus, optionally, a PR.
- If a blocker needs a second app (e.g. an external database), say so explicitly
  and point at `/argocd-add-chart` + `/argocd-deploy`; do not scaffold it here.
