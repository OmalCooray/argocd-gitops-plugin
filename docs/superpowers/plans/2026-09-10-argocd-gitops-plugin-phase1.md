# ArgoCD GitOps Plugin — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1 core of `argocd-gitops-plugin` — a Claude Code plugin that scaffolds an Argo CD GitOps repo (catalog + environments + root app), onboards Helm charts, deploys them to an environment, bootstraps Argo CD onto a cluster, and audits drift.

**Architecture:** A standard Claude Code plugin: `.claude-plugin/plugin.json` manifest, `commands/*.md` slash commands, `skills/*/SKILL.md` knowledge modules, `agents/*.md` subagents, plus a `templates/` directory of literal file templates the skills render from. Commands are CLI-first (`git`, `gh`, `helm`, `kubectl`, `argocd`) and never require an MCP server. A `tests/` directory holds shell + Python checks that render templates and validate generated Argo CD / Helm artifacts with real tools.

**Tech Stack:** Markdown (commands/agents/skills), JSON (manifest, `.mcp.json`), Helm 3, Argo CD CLI, `kubectl`, `gh` CLI, Bash, Python 3 (validation scripts, `pytest`).

**Phase 1 scope (from the spec):**
- Plugin scaffold + `templates/`
- Skills: `argocd-repo-conventions`, `helm-chart-onboarding`
- Commands: `/argocd-init-repo`, `/argocd-add-chart`, `/argocd-deploy`, `/argocd-bootstrap`, `/argocd-audit`
- Agent: `argocd-onboarder`
- `.mcp.json` with the Akuity Argo CD MCP server defined but disabled
- Git branch + PR flow via `gh`

**Out of scope (later phases):** `values-review`, `argocd-troubleshooting`, `/argocd-doctor`, `/argocd-review-values`, `/argocd-review-pr`, `argocd-doctor` agent, `/argocd-add-env`, `/argocd-promote`, secrets.

**Environment notes (verified on this machine 2026-09-10):**
- Available: `git` 2.45, `helm` v3.19, `kubectl` v1.32 (context `docker-desktop`, a live single-node cluster), `node` v24, `python` 3.12.
- NOT installed: `gh`, `argocd`, `yq`, `jq`. Tasks that need `gh`/`argocd` note this; their verification either installs the tool or is review-only. The `docker-desktop` cluster is used for real `helm template` / `kubectl apply --dry-run` / end-to-end Argo CD install checks.

**Repo:** `C:\claude\argocd-gitops-plugin` (git initialised, `master` branch, user `Omal Cooray <omalcooray9@gmail.com>`). The design spec is at `docs/superpowers/specs/2026-09-10-argocd-gitops-plugin-design.md`.

**Conventions for every task:**
- Work on `master` directly (solo plugin repo, Phase 1). Commit after each task.
- Commit message trailer (required):
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  ```
- Line endings: repo has `* text=auto`; write LF, let git normalise.
- All paths below are relative to `C:\claude\argocd-gitops-plugin`.

---

## File Structure

Created by this plan:

```
argocd-gitops-plugin/
├── .claude-plugin/
│   └── plugin.json                         # manifest (name, version, metadata)
├── .mcp.json                               # Akuity Argo CD MCP, disabled (documented)
├── README.md                               # what it is, deps, install, command index
├── .gitattributes                          # text=auto normalisation
├── commands/
│   ├── argocd-bootstrap.md                 # /argocd-bootstrap [kube-context]
│   ├── argocd-init-repo.md                 # /argocd-init-repo <name>
│   ├── argocd-add-chart.md                 # /argocd-add-chart <name> [version]
│   ├── argocd-deploy.md                    # /argocd-deploy <app> <env>
│   └── argocd-audit.md                     # /argocd-audit [env]
├── skills/
│   ├── argocd-repo-conventions/
│   │   ├── SKILL.md                        # layout, naming, manifest wiring, tracking model
│   │   └── reference/
│   │       ├── repo-layout.md              # annotated tree + rationale
│   │       └── application-manifest.md     # multi-source Application spec, field by field
│   └── helm-chart-onboarding/
│       ├── SKILL.md                        # find → pin → pull values → minimal override
│       └── reference/
│           └── artifacthub-api.md          # ArtifactHub REST endpoints used via WebFetch
├── agents/
│   └── argocd-onboarder.md                 # research → scaffold catalog → deploy → PR
├── templates/
│   ├── Chart.yaml.tmpl                     # umbrella chart w/ pinned dependency
│   ├── values.yaml.tmpl                    # starter override file (commented)
│   ├── application.yaml.tmpl               # multi-source Argo CD Application
│   ├── root.yaml.tmpl                      # root app-of-apps Application
│   ├── install.sh.tmpl                     # Argo CD bootstrap script
│   ├── gitops-README.md.tmpl               # README for a generated GitOps repo
│   ├── gitops-CLAUDE.md.tmpl               # .claude/CLAUDE.md for a generated repo
│   └── CODEOWNERS.tmpl                     # prod path ownership
├── tests/
│   ├── README.md                          # how to run the suite + prerequisites
│   ├── render.py                           # tiny {{VAR}} template renderer (no deps)
│   ├── fixtures/
│   │   ├── podinfo.vars.json               # sample vars for a known small chart
│   │   └── golden/                         # expected rendered outputs
│   │       ├── Chart.yaml
│   │       ├── application.yaml
│   │       └── root.yaml
│   ├── test_manifest.py                    # plugin.json + .mcp.json validity/shape
│   ├── test_templates.py                   # render templates → compare to golden
│   ├── test_plugin_components.py           # frontmatter + naming + discovery rules
│   └── smoke/
│       ├── helm_smoke.sh                   # build a wrapper chart from templates, helm lint/template
│       └── argocd_e2e.sh                   # install Argo CD on docker-desktop, apply root app, verify
└── docs/
    └── superpowers/
        ├── specs/2026-09-10-argocd-gitops-plugin-design.md   # (exists)
        └── plans/2026-09-10-argocd-gitops-plugin-phase1.md   # (this file)
```

---

## Task 1: `.gitattributes` and repo hygiene

**Files:**
- Create: `.gitattributes`
- Modify: `.gitignore` (exists — append)

- [ ] **Step 1: Write `.gitattributes`**

```gitattributes
* text=auto eol=lf
*.png binary
*.sh text eol=lf
```

- [ ] **Step 2: Append to `.gitignore`**

Append these lines to the existing `.gitignore`:

```gitignore
# test artifacts
tests/.out/
tests/**/__pycache__/
.pytest_cache/
```

- [ ] **Step 3: Verify git sees the files**

Run: `git status --porcelain`
Expected: two lines — `AM .gitignore` (or ` M`) and `?? .gitattributes` (statuses may vary; both files must appear).

- [ ] **Step 4: Commit**

```bash
git add .gitattributes .gitignore
git commit -m "chore: add gitattributes and test ignores

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: Plugin manifest

**Files:**
- Create: `.claude-plugin/plugin.json`
- Test: `tests/test_manifest.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_manifest.py`:

```python
"""Validate the plugin manifest and .mcp.json shape."""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_manifest_exists_and_is_json():
    data = load(".claude-plugin/plugin.json")
    assert isinstance(data, dict)


def test_manifest_name_is_kebab_case():
    data = load(".claude-plugin/plugin.json")
    assert data["name"] == "argocd-gitops-plugin"
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", data["name"])


def test_manifest_has_semver_version():
    data = load(".claude-plugin/plugin.json")
    assert re.fullmatch(r"\d+\.\d+\.\d+", data["version"])


def test_manifest_has_description_and_author():
    data = load(".claude-plugin/plugin.json")
    assert data["description"].strip()
    assert data["author"]["name"] == "Omal Cooray"


def test_manifest_declares_no_custom_component_paths():
    # Phase 1 uses only default auto-discovery dirs.
    data = load(".claude-plugin/plugin.json")
    for key in ("commands", "agents", "skills", "hooks"):
        assert key not in data, f"unexpected custom path for {key}"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_manifest.py -q`
Expected: FAIL — `FileNotFoundError` / errors collecting, because `.claude-plugin/plugin.json` does not exist yet.

- [ ] **Step 3: Write `.claude-plugin/plugin.json`**

```json
{
  "name": "argocd-gitops-plugin",
  "version": "0.1.0",
  "description": "Scaffold and operate an Argo CD GitOps repo: bootstrap Argo CD, onboard Helm charts into a catalog, deploy apps to environments via app-of-apps, and audit drift.",
  "author": {
    "name": "Omal Cooray",
    "email": "omalcooray9@gmail.com"
  },
  "repository": "https://github.com/OmalCooray/argocd-gitops-plugin",
  "license": "MIT",
  "keywords": ["argocd", "gitops", "helm", "kubernetes", "app-of-apps"]
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_manifest.py -q`
Expected: PASS (5 passed). `test_manifest.py` still references `.mcp.json`? No — the `.mcp.json` tests are added in Task 12. All 5 tests here pass now.

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/plugin.json tests/test_manifest.py
git commit -m "feat: add plugin manifest

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: Template renderer + fixtures

The plugin's skills tell Claude to copy a template and substitute `{{VAR}}` placeholders. `tests/render.py` is a dependency-free renderer used only by the test suite to prove the templates produce exactly the intended output.

**Files:**
- Create: `tests/render.py`
- Create: `tests/fixtures/podinfo.vars.json`
- Test: `tests/test_templates.py` (written here, fails until Task 4 adds templates)

- [ ] **Step 1: Write `tests/render.py`**

```python
"""Minimal mustache-style renderer: replaces {{ KEY }} with vars[KEY].

Rules:
- {{ KEY }} and {{KEY}} both work (surrounding spaces ignored).
- Every placeholder in the template MUST have a key in vars, else KeyError.
- Values are inserted literally (no escaping — these are YAML/text templates).
"""
from __future__ import annotations
import json
import re
import sys

_PLACEHOLDER = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")


def render(template: str, variables: dict) -> str:
    def sub(match: re.Match) -> str:
        key = match.group(1)
        if key not in variables:
            raise KeyError(f"missing template variable: {key}")
        return str(variables[key])

    return _PLACEHOLDER.sub(sub, template)


def placeholders(template: str) -> set[str]:
    return set(_PLACEHOLDER.findall(template))


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: render.py <template-file> <vars.json>", file=sys.stderr)
        return 2
    template = open(argv[1], encoding="utf-8").read()
    variables = json.loads(open(argv[2], encoding="utf-8").read())
    sys.stdout.write(render(template, variables))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 2: Write `tests/fixtures/podinfo.vars.json`**

`podinfo` is a tiny, stable public Helm chart (`oci://ghcr.io/stefanprodan/charts/podinfo`), ideal as a test fixture.

```json
{
  "APP_NAME": "podinfo",
  "CHART_NAME": "podinfo",
  "CHART_VERSION": "6.9.0",
  "CHART_REPO_URL": "https://stefanprodan.github.io/podinfo",
  "NAMESPACE": "podinfo",
  "ENV_NAME": "data-platform",
  "GITOPS_REPO_URL": "https://github.com/OmalCooray/data-platform-k8s-configs",
  "TARGET_REVISION": "master",
  "ARGOCD_NAMESPACE": "argocd",
  "DEST_SERVER": "https://kubernetes.default.svc"
}
```

- [ ] **Step 3: Write `tests/test_templates.py`**

```python
"""Render each template with fixture vars and compare against golden files."""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from render import render, placeholders  # noqa: E402

VARS = json.loads((ROOT / "tests/fixtures/podinfo.vars.json").read_text())

CASES = [
    ("templates/Chart.yaml.tmpl", "tests/fixtures/golden/Chart.yaml"),
    ("templates/application.yaml.tmpl", "tests/fixtures/golden/application.yaml"),
    ("templates/root.yaml.tmpl", "tests/fixtures/golden/root.yaml"),
]


@pytest.mark.parametrize("tmpl,golden", CASES)
def test_template_renders_to_golden(tmpl, golden):
    template_text = (ROOT / tmpl).read_text(encoding="utf-8")
    expected = (ROOT / golden).read_text(encoding="utf-8")
    assert render(template_text, VARS) == expected


@pytest.mark.parametrize("tmpl,_golden", CASES)
def test_every_placeholder_has_a_fixture_var(tmpl, _golden):
    template_text = (ROOT / tmpl).read_text(encoding="utf-8")
    missing = placeholders(template_text) - set(VARS)
    assert not missing, f"{tmpl} uses vars with no fixture value: {sorted(missing)}"
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `python -m pytest tests/test_templates.py -q`
Expected: FAIL — `FileNotFoundError` for `templates/Chart.yaml.tmpl` (templates come in Task 4).

- [ ] **Step 5: Sanity-check the renderer in isolation**

Run:
```bash
python -c "import sys; sys.path.insert(0,'tests'); from render import render; print(render('name: {{ APP_NAME }}', {'APP_NAME':'x'}))"
```
Expected output: `name: x`

- [ ] **Step 6: Commit**

```bash
git add tests/render.py tests/fixtures/podinfo.vars.json tests/test_templates.py
git commit -m "test: add template renderer and fixture vars

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: File templates + golden files

**Files:**
- Create: `templates/Chart.yaml.tmpl`, `templates/values.yaml.tmpl`, `templates/application.yaml.tmpl`, `templates/root.yaml.tmpl`, `templates/install.sh.tmpl`, `templates/gitops-README.md.tmpl`, `templates/gitops-CLAUDE.md.tmpl`, `templates/CODEOWNERS.tmpl`
- Create: `tests/fixtures/golden/Chart.yaml`, `tests/fixtures/golden/application.yaml`, `tests/fixtures/golden/root.yaml`

- [ ] **Step 1: Write `templates/Chart.yaml.tmpl`**

```yaml
apiVersion: v2
name: {{ APP_NAME }}
description: Wrapper chart for {{ APP_NAME }} ({{ CHART_NAME }} {{ CHART_VERSION }})
type: application
version: 0.1.0
appVersion: "{{ CHART_VERSION }}"
dependencies:
  - name: {{ CHART_NAME }}
    version: {{ CHART_VERSION }}
    repository: {{ CHART_REPO_URL }}
```

- [ ] **Step 2: Write `templates/values.yaml.tmpl`**

```yaml
# Overrides for the upstream chart "{{ CHART_NAME }}".
# Everything nests under the dependency name so Helm routes it to the subchart.
# Pull the upstream defaults with:
#   helm show values {{ CHART_NAME }} --repo {{ CHART_REPO_URL }} --version {{ CHART_VERSION }}
# then copy ONLY the keys you are changing under the block below.
{{ CHART_NAME }}:
  # image:
  #   tag: "{{ CHART_VERSION }}"
```

- [ ] **Step 3: Write `templates/application.yaml.tmpl`**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {{ APP_NAME }}
  namespace: {{ ARGOCD_NAMESPACE }}
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  sources:
    - repoURL: {{ GITOPS_REPO_URL }}
      targetRevision: {{ TARGET_REVISION }}
      path: charts/{{ APP_NAME }}
      helm:
        valueFiles:
          - $values/environments/{{ ENV_NAME }}/values/{{ APP_NAME }}.yaml
    - repoURL: {{ GITOPS_REPO_URL }}
      targetRevision: {{ TARGET_REVISION }}
      ref: values
  destination:
    server: {{ DEST_SERVER }}
    namespace: {{ NAMESPACE }}
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

- [ ] **Step 4: Write `templates/root.yaml.tmpl`**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root-{{ ENV_NAME }}
  namespace: {{ ARGOCD_NAMESPACE }}
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: {{ GITOPS_REPO_URL }}
    targetRevision: {{ TARGET_REVISION }}
    path: environments/{{ ENV_NAME }}/apps
    directory:
      recurse: false
  destination:
    server: {{ DEST_SERVER }}
    namespace: {{ ARGOCD_NAMESPACE }}
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=false
```

- [ ] **Step 5: Write `templates/install.sh.tmpl`**

```bash
#!/usr/bin/env bash
# Bootstrap Argo CD onto the current kube-context, then hand control to Git.
#
# Usage:  ./bootstrap/install.sh [kube-context]
#
# Idempotent: safe to re-run. After the first run, Argo CD manages everything
# else (including itself if you add an app for it) from {{ GITOPS_REPO_URL }}.
set -euo pipefail

ARGOCD_NAMESPACE="{{ ARGOCD_NAMESPACE }}"
ARGOCD_CHART_VERSION="{{ ARGOCD_CHART_VERSION }}"
ENV_NAME="{{ ENV_NAME }}"
CONTEXT="${1:-$(kubectl config current-context)}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo ">> Using kube-context: ${CONTEXT}"
kubectl --context "${CONTEXT}" cluster-info >/dev/null

echo ">> Installing/upgrading Argo CD (chart ${ARGOCD_CHART_VERSION}) into ${ARGOCD_NAMESPACE}"
helm repo add argo https://argoproj.github.io/argo-helm >/dev/null 2>&1 || true
helm repo update argo >/dev/null
helm --kube-context "${CONTEXT}" upgrade --install argo-cd argo/argo-cd \
  --namespace "${ARGOCD_NAMESPACE}" --create-namespace \
  --version "${ARGOCD_CHART_VERSION}" \
  --wait

echo ">> Waiting for Argo CD CRDs to register"
kubectl --context "${CONTEXT}" wait --for=condition=Established \
  crd/applications.argoproj.io crd/appprojects.argoproj.io --timeout=120s

echo ">> Applying the root application for environment '${ENV_NAME}'"
kubectl --context "${CONTEXT}" apply -n "${ARGOCD_NAMESPACE}" \
  -f "${REPO_ROOT}/environments/${ENV_NAME}/root.yaml"

echo ">> Done. Watch sync status with:  argocd app list   (or the Argo CD UI)"
```

- [ ] **Step 6: Write `templates/gitops-README.md.tmpl`**

```markdown
# {{ GITOPS_REPO_NAME }}

Argo CD GitOps configuration, managed with the
[`argocd-gitops-plugin`](https://github.com/OmalCooray/argocd-gitops-plugin).

## Layout

| Path | Purpose |
|------|---------|
| `charts/<app>/` | Catalog: a Helm wrapper chart per app (`Chart.yaml` pins the upstream chart, `values.yaml` holds base overrides). Nothing here deploys on its own. |
| `environments/<env>/apps/<app>.yaml` | An Argo CD `Application` — the fact that `<app>` is deployed to `<env>`. |
| `environments/<env>/values/<app>.yaml` | Optional per-environment value overlay. |
| `environments/<env>/root.yaml` | The root app-of-apps for `<env>`; syncs everything in that `apps/` folder. |
| `bootstrap/install.sh` | One-time Argo CD install for a fresh cluster. |

## First-time setup

```bash
./bootstrap/install.sh {{ ENV_NAME }}
```

## Day-to-day (via the plugin)

- Add a chart to the catalog: `/argocd-add-chart <name> [version]`
- Deploy it to an environment: `/argocd-deploy <app> <env>`
- Check for drift: `/argocd-audit [env]`
```

- [ ] **Step 7: Write `templates/gitops-CLAUDE.md.tmpl`**

```markdown
# Repo facts for Claude

This is an Argo CD GitOps repo managed with `argocd-gitops-plugin`. Read the
plugin skill `argocd-repo-conventions` before generating or editing any file here.

- GitOps repo URL: {{ GITOPS_REPO_URL }}
- Default branch: {{ TARGET_REVISION }}
- Argo CD namespace: {{ ARGOCD_NAMESPACE }}
- Environments: {{ ENV_NAME }}
- Destination cluster for {{ ENV_NAME }}: {{ DEST_SERVER }}

## Catalog inventory

_(Updated by `/argocd-add-chart`.)_

| App | Upstream chart | Version | Repo |
|-----|----------------|---------|------|

## Deployment matrix

_(Updated by `/argocd-deploy`.)_

| App | {{ ENV_NAME }} |
|-----|----------------|
```

- [ ] **Step 8: Write `templates/CODEOWNERS.tmpl`**

```
# Write access control for environment config.
# Phase 1 has one environment; prod rules are added when a prod env is created.
/environments/{{ ENV_NAME }}/   @OmalCooray
```

- [ ] **Step 9: Write the golden files**

`tests/fixtures/golden/Chart.yaml` — exactly what `Chart.yaml.tmpl` renders with `podinfo.vars.json`:

```yaml
apiVersion: v2
name: podinfo
description: Wrapper chart for podinfo (podinfo 6.9.0)
type: application
version: 0.1.0
appVersion: "6.9.0"
dependencies:
  - name: podinfo
    version: 6.9.0
    repository: https://stefanprodan.github.io/podinfo
```

`tests/fixtures/golden/application.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: podinfo
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  sources:
    - repoURL: https://github.com/OmalCooray/data-platform-k8s-configs
      targetRevision: master
      path: charts/podinfo
      helm:
        valueFiles:
          - $values/environments/data-platform/values/podinfo.yaml
    - repoURL: https://github.com/OmalCooray/data-platform-k8s-configs
      targetRevision: master
      ref: values
  destination:
    server: https://kubernetes.default.svc
    namespace: podinfo
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

`tests/fixtures/golden/root.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root-data-platform
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/OmalCooray/data-platform-k8s-configs
    targetRevision: master
    path: environments/data-platform/apps
    directory:
      recurse: false
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=false
```

- [ ] **Step 10: Add the `ARGOCD_CHART_VERSION` and `GITOPS_REPO_NAME` fixture vars**

`install.sh.tmpl` and `gitops-README.md.tmpl` introduce two placeholders not in the fixture. Add them to `tests/fixtures/podinfo.vars.json` so the "every placeholder has a fixture var" test covers them:

```json
{
  "APP_NAME": "podinfo",
  "CHART_NAME": "podinfo",
  "CHART_VERSION": "6.9.0",
  "CHART_REPO_URL": "https://stefanprodan.github.io/podinfo",
  "NAMESPACE": "podinfo",
  "ENV_NAME": "data-platform",
  "GITOPS_REPO_URL": "https://github.com/OmalCooray/data-platform-k8s-configs",
  "GITOPS_REPO_NAME": "data-platform-k8s-configs",
  "TARGET_REVISION": "master",
  "ARGOCD_NAMESPACE": "argocd",
  "ARGOCD_CHART_VERSION": "7.7.0",
  "DEST_SERVER": "https://kubernetes.default.svc"
}
```

- [ ] **Step 11: Extend `tests/test_templates.py` to cover the text templates**

Add these cases to the `CASES` list is NOT wanted (no golden for scripts). Instead add a separate test that just renders them and checks no placeholder remains:

```python
TEXT_ONLY = [
    "templates/values.yaml.tmpl",
    "templates/install.sh.tmpl",
    "templates/gitops-README.md.tmpl",
    "templates/gitops-CLAUDE.md.tmpl",
    "templates/CODEOWNERS.tmpl",
]


@pytest.mark.parametrize("tmpl", TEXT_ONLY)
def test_text_template_fully_renders(tmpl):
    template_text = (ROOT / tmpl).read_text(encoding="utf-8")
    out = render(template_text, VARS)
    assert "{{" not in out and "}}" not in out
    missing = placeholders(template_text) - set(VARS)
    assert not missing, f"{tmpl} uses vars with no fixture value: {sorted(missing)}"
```

- [ ] **Step 12: Run the template tests**

Run: `python -m pytest tests/test_templates.py -q`
Expected: PASS — 3 golden-match tests + 3 placeholder tests + 5 text-render tests = 11 passed. If a golden mismatch appears, fix the golden file to match the template output byte-for-byte (the template is the source of truth for structure; the golden encodes the exact expected string).

- [ ] **Step 13: Helm-lint the rendered wrapper chart (real tool)**

Run:
```bash
mkdir -p tests/.out/podinfo
python tests/render.py templates/Chart.yaml.tmpl tests/fixtures/podinfo.vars.json > tests/.out/podinfo/Chart.yaml
python tests/render.py templates/values.yaml.tmpl tests/fixtures/podinfo.vars.json > tests/.out/podinfo/values.yaml
helm dependency build tests/.out/podinfo
helm lint tests/.out/podinfo
```
Expected: `helm dependency build` downloads `podinfo-6.9.0.tgz`; `helm lint` prints `1 chart(s) linted, 0 chart(s) failed`.
(If `podinfo` 6.9.0 is unavailable, run `helm show chart podinfo --repo https://stefanprodan.github.io/podinfo` to get the current version and update `CHART_VERSION` in the fixture + golden `Chart.yaml` + the `appVersion` line, then re-run Steps 12–13.)

- [ ] **Step 14: Dry-run the rendered Application against the cluster (real tool)**

Run:
```bash
python tests/render.py templates/application.yaml.tmpl tests/fixtures/podinfo.vars.json | kubectl apply --dry-run=client -f -
python tests/render.py templates/root.yaml.tmpl tests/fixtures/podinfo.vars.json | kubectl apply --dry-run=client -f -
```
Expected: each prints `application.argoproj.io/... created (dry run)` OR fails only with `no matches for kind "Application"` if Argo CD CRDs are not installed. The latter is acceptable at this stage — re-verified in Task 13's e2e. A YAML *parse* error is a real failure; fix the template.

- [ ] **Step 15: Commit**

```bash
git add templates/ tests/fixtures/ tests/test_templates.py
git commit -m "feat: add file templates with golden-file coverage

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: Plugin component structural test

**Files:**
- Create: `tests/test_plugin_components.py`

- [ ] **Step 1: Write the test**

```python
"""Structural checks for commands, agents, and skills."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

EXPECTED_COMMANDS = {
    "argocd-bootstrap", "argocd-init-repo", "argocd-add-chart",
    "argocd-deploy", "argocd-audit",
}
EXPECTED_SKILLS = {"argocd-repo-conventions", "helm-chart-onboarding"}
EXPECTED_AGENTS = {"argocd-onboarder"}

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _frontmatter(path: pathlib.Path) -> str:
    m = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    assert m, f"{path} has no YAML frontmatter"
    return m.group(1)


def test_expected_commands_present_and_named():
    files = {p.stem for p in (ROOT / "commands").glob("*.md")}
    assert EXPECTED_COMMANDS <= files, EXPECTED_COMMANDS - files
    for name in EXPECTED_COMMANDS:
        fm = _frontmatter(ROOT / "commands" / f"{name}.md")
        assert "description:" in fm


def test_expected_skills_have_skill_md_with_name_and_description():
    for name in EXPECTED_SKILLS:
        skill = ROOT / "skills" / name / "SKILL.md"
        assert skill.exists(), skill
        fm = _frontmatter(skill)
        assert re.search(r"^name:\s*\S", fm, re.MULTILINE)
        assert re.search(r"^description:\s*\S", fm, re.MULTILINE)


def test_expected_agents_present_with_description():
    for name in EXPECTED_AGENTS:
        agent = ROOT / "agents" / f"{name}.md"
        assert agent.exists(), agent
        assert "description:" in _frontmatter(agent)


def test_no_hardcoded_home_paths_in_components():
    offenders = []
    for sub in ("commands", "agents", "skills"):
        for p in (ROOT / sub).rglob("*.md"):
            text = p.read_text(encoding="utf-8")
            if re.search(r"/(Users|home)/[a-z]", text) or "C:\\\\Users" in text:
                offenders.append(str(p))
    assert not offenders, offenders
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_plugin_components.py -q`
Expected: FAIL — commands/skills/agents directories don't exist yet (`EXPECTED_COMMANDS - files` shows all five).

- [ ] **Step 3: Commit the test**

```bash
git add tests/test_plugin_components.py
git commit -m "test: add plugin component structural checks

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 6: Skill — `argocd-repo-conventions`

**Files:**
- Create: `skills/argocd-repo-conventions/SKILL.md`
- Create: `skills/argocd-repo-conventions/reference/repo-layout.md`
- Create: `skills/argocd-repo-conventions/reference/application-manifest.md`

- [ ] **Step 1: Write `skills/argocd-repo-conventions/SKILL.md`**

Frontmatter + body. Keep the body under ~150 lines; push detail to `reference/`.

```markdown
---
name: argocd-repo-conventions
description: Conventions for an Argo CD GitOps repo managed by argocd-gitops-plugin — the catalog + environments layout, file naming, how Application manifests wire charts to per-environment values, and the dev/prod revision-tracking model. Load before creating or editing any file in such a repo.
---

# Argo CD GitOps repo conventions

## Mental model

Two separate concerns, two separate directory trees:

1. **Catalog** (`charts/<app>/`) — a Helm *wrapper chart* per app. Declares the
   upstream chart as a dependency and holds environment-agnostic base overrides.
   A folder here deploys **nothing** by itself.
2. **Deployment set** (`environments/<env>/`) — which apps run on which cluster.
   An `Application` manifest in `environments/<env>/apps/` is the *fact* that
   `<app>` is deployed to `<env>`.

The **root application** (`environments/<env>/root.yaml`) is an app-of-apps that
syncs every `Application` in that environment's `apps/` folder. Applying it once
replaces any hand-run reconcile script.

## Directory layout

See `reference/repo-layout.md` for the annotated tree. Summary:

```
charts/<app>/{Chart.yaml,values.yaml}
environments/<env>/root.yaml
environments/<env>/apps/<app>.yaml
environments/<env>/values/<app>.yaml      # optional overlay
bootstrap/install.sh
.claude/CLAUDE.md
CODEOWNERS
```

## Naming rules

- `<app>` — kebab-case, matches the catalog folder name, the `Application`
  `metadata.name`, and the file stem in `apps/` and `values/`.
- One upstream chart per catalog entry. If you need two, make two entries.
- `<env>` — kebab-case cluster/environment name (e.g. `data-platform`, `prod`).
- Wrapper chart `version` starts at `0.1.0` and is bumped when the *wrapper*
  changes; `appVersion` mirrors the upstream chart version.

## Wrapper chart

`Chart.yaml` — `apiVersion: v2`, one entry under `dependencies` pinning the
upstream chart by exact version (never a range, never `*`).

`values.yaml` — overrides nest under the **dependency name** so Helm routes them
to the subchart:

```yaml
<chart-name>:
  image:
    tag: "x.y.z"
```

Get upstream defaults with `helm show values <chart> --repo <url> --version <v>`
and copy only the keys you change.

## Application manifest

Multi-source spec — see `reference/application-manifest.md` for every field.
Key points:
- source 1: `path: charts/<app>`, `helm.valueFiles: [$values/environments/<env>/values/<app>.yaml]`
- source 2: same repo, `ref: values` (this is what `$values` resolves to)
- `syncPolicy.automated` with `prune: true`, `selfHeal: true`
- `syncOptions: [CreateNamespace=true, ServerSideApply=true]`
- requires **Argo CD ≥ 2.6** (multi-source apps). Note this in the repo README.

## Revision-tracking model

- `environments/dev/apps/*.yaml` → `targetRevision: <default-branch>` — auto-syncs
  on merge, for fast iteration.
- `environments/prod/apps/*.yaml` → `targetRevision: <git-sha-or-tag>` — moves
  only via an explicit PR that bumps the pin.
- Environments are **directories, not branches**. Promotion is a PR editing the
  target env's `values/<app>.yaml` or bumping its `targetRevision`. Never
  merge one environment branch into another.

## When editing an existing repo

Read `.claude/CLAUDE.md` first for repo-specific facts (repo URL, env names,
Argo CD namespace, catalog inventory). Follow the existing file style exactly.
```

- [ ] **Step 2: Write `skills/argocd-repo-conventions/reference/repo-layout.md`**

```markdown
# Annotated repo layout

```
<gitops-repo>/
├── charts/                          # CATALOG
│   └── <app>/
│       ├── Chart.yaml               # apiVersion v2; upstream chart pinned in dependencies
│       └── values.yaml              # base overrides, nested under the dependency name
│
├── environments/
│   └── <env>/                       # one folder per cluster/environment
│       ├── root.yaml                # root app-of-apps → path: environments/<env>/apps
│       ├── apps/
│       │   └── <app>.yaml           # Argo CD Application (multi-source)
│       └── values/
│           └── <app>.yaml           # optional per-env Helm values overlay
│
├── bootstrap/
│   └── install.sh                   # helm upgrade --install argo-cd + kubectl apply root.yaml
│
├── .claude/
│   └── CLAUDE.md                    # repo facts + catalog inventory + deployment matrix
├── CODEOWNERS
└── README.md
```

## Why this shape

- **Catalog reuse across environments**: three environments deploying `metabase`
  share one `charts/metabase/`. No chart duplication, no drift.
- **Selective deployment**: `charts/` may hold 50 apps; an environment's
  `apps/` folder contains only the handful that run there.
- **Additive multi-env**: a new cluster is a new `environments/<name>/` folder
  plus one `kubectl apply` of its `root.yaml`. Nothing else moves.
- **Greppable env delta**: `diff environments/dev environments/prod` shows the
  entire intentional difference between environments.

## Adding an environment later

```
environments/
├── data-platform/      # existing, untouched
└── prod/               # new: root.yaml + apps/ (subset) + values/ (overrides)
```
```

- [ ] **Step 3: Write `skills/argocd-repo-conventions/reference/application-manifest.md`**

```markdown
# The multi-source Application manifest, field by field

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: <app>                        # == catalog folder == file stem
  namespace: <argocd-namespace>      # where Argo CD runs, usually "argocd"
  finalizers:
    - resources-finalizer.argocd.argoproj.io   # cascade-delete children on app delete
spec:
  project: default
  sources:
    - repoURL: <gitops-repo-url>
      targetRevision: <branch-or-sha>          # branch for dev, pinned sha/tag for prod
      path: charts/<app>                        # the wrapper chart
      helm:
        valueFiles:
          - $values/environments/<env>/values/<app>.yaml   # resolved from the ref below
    - repoURL: <gitops-repo-url>
      targetRevision: <branch-or-sha>
      ref: values                               # makes $values point at this repo checkout
  destination:
    server: <dest-cluster-api>                  # https://kubernetes.default.svc for in-cluster
    namespace: <app-namespace>                  # where the workload runs
  syncPolicy:
    automated:
      prune: true                               # delete resources removed from git
      selfHeal: true                            # revert manual kubectl drift
    syncOptions:
      - CreateNamespace=true                    # make destination.namespace if absent
      - ServerSideApply=true                    # avoids last-applied annotation bloat on big CRDs
```

## Gotchas

- The `$values` ref requires **Argo CD ≥ 2.6**. Older versions: drop source 2 and
  inline the overlay into source 1's `helm.values` (string), or skip the overlay.
- If `environments/<env>/values/<app>.yaml` does not exist, Argo CD sync fails
  with "values file not found". `/argocd-deploy` always creates at least an empty
  (comment-only) overlay file.
- `finalizers` makes `argocd app delete` / removing the file also delete the
  workload. Omit it only if you want the app removed from Argo CD but left running.
- Multi-source apps show sources by index in the UI; name them in PR descriptions.
```

- [ ] **Step 4: Run the component test — skills portion**

Run: `python -m pytest tests/test_plugin_components.py::test_expected_skills_have_skill_md_with_name_and_description -q`
Expected: still FAIL (only 1 of 2 skills exists) — `helm-chart-onboarding` is Task 7. That's fine; the assertion lists the missing skill.

- [ ] **Step 5: Commit**

```bash
git add skills/argocd-repo-conventions/
git commit -m "feat: add argocd-repo-conventions skill

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 7: Skill — `helm-chart-onboarding`

**Files:**
- Create: `skills/helm-chart-onboarding/SKILL.md`
- Create: `skills/helm-chart-onboarding/reference/artifacthub-api.md`

- [ ] **Step 1: Write `skills/helm-chart-onboarding/SKILL.md`**

```markdown
---
name: helm-chart-onboarding
description: How to take an upstream Helm chart into the Argo CD catalog — locate it (ArtifactHub / helm repo search), choose and pin an exact version, pull its default values, and produce a minimal override file. Load when adding a chart to a GitOps repo's charts/ directory.
---

# Helm chart onboarding

## Goal

Produce `charts/<app>/Chart.yaml` (wrapper) and `charts/<app>/values.yaml`
(minimal override) for an upstream chart, with an **exact** pinned version.

## Step 1 — locate the chart

If the user gave a repo URL, use it. Otherwise search:

- `helm search hub <term> --max-col-width 0` — searches ArtifactHub.
- Or query the ArtifactHub REST API for the canonical repo URL and versions —
  see `reference/artifacthub-api.md`. Use WebFetch; no API key needed.

Prefer the **official / vendor** repo over re-packagers. Record the
`repository` URL (the Helm repo, e.g. `https://charts.bitnami.com/bitnami`, not
the ArtifactHub page).

## Step 2 — choose a version

- List versions: `helm search repo <repo>/<chart> --versions` (after
  `helm repo add`), or the ArtifactHub API.
- Default to the **latest stable** (non-`-rc`, non-`-beta`) unless the user names
  one, or unless the latest requires a Kubernetes version newer than the target
  cluster (`helm show chart ... | grep kubeVersion`).
- Pin the **exact** version. Never a range, never `*`, never omit.

## Step 3 — pull upstream defaults

```bash
helm show values <chart> --repo <repo-url> --version <version> > /tmp/<app>-upstream-values.yaml
```

Read it. Identify the handful of keys that matter for a first deploy:
image/tag (if you want to pin harder), ingress, persistence, resources,
replica count, service type. **Do not** copy the whole file.

## Step 4 — write the wrapper

Render `templates/Chart.yaml.tmpl` and `templates/values.yaml.tmpl` from the
plugin with: `APP_NAME`, `CHART_NAME`, `CHART_VERSION`, `CHART_REPO_URL`.

The override file nests everything under the **chart name** (the dependency
name), because that is how Helm routes subchart values:

```yaml
<chart-name>:
  <only the keys you are changing>
```

## Step 5 — verify locally before committing

```bash
helm dependency build charts/<app>
helm lint charts/<app>
helm template charts/<app> | kubectl apply --dry-run=client -f -   # if a cluster is reachable
```

All three must pass. `helm dependency build` writes `Chart.lock` and
`charts/*.tgz` — add `charts/<app>/charts/` and `Chart.lock` handling per the
repo's `.gitignore` (default: commit `Chart.lock`, ignore the `.tgz`).

## Step 6 — update the catalog inventory

Add a row to `.claude/CLAUDE.md`'s "Catalog inventory" table:
`| <app> | <chart> | <version> | <repo-url> |`.
```

- [ ] **Step 2: Write `skills/helm-chart-onboarding/reference/artifacthub-api.md`**

```markdown
# ArtifactHub REST API (used via WebFetch)

Base: `https://artifacthub.io/api/v1`. No auth for reads.

## Search for a chart

```
GET /packages/search?kind=0&ts_query_web=<term>&limit=20
```
`kind=0` = Helm charts. Response: `packages[]` with `name`, `repository.name`,
`repository.url`, `version` (latest), `official`, `cncf`.

## Get a specific chart's detail + version list

```
GET /packages/helm/<repo-name>/<chart-name>
```
Returns `version` (latest), `available_versions[]` (each with `version`,
`ts`, `contains_security_updates`, `prerelease`), `repository.url`,
`data.kubeVersion` (constraint string), `data.dependencies[]`.

## Get one exact version

```
GET /packages/helm/<repo-name>/<chart-name>/<version>
```

## Picking a version programmatically

1. Filter `available_versions` to `prerelease == false`.
2. Sort by semver descending.
3. Take the first whose `data.kubeVersion` (if present) is satisfied by the
   target cluster's server version (`kubectl version -o json`).

## Notes

- The `repository.url` from the API is the **Helm repo URL** — use it directly in
  `Chart.yaml` `dependencies[].repository` and `helm show values --repo`.
- Some charts are OCI (`repository.url` starts with `oci://`). For OCI,
  `Chart.yaml` `repository` is the `oci://...` path and `helm show values` takes
  the full `oci://.../<chart>` reference with `--version`.
```

- [ ] **Step 3: Run the skills structural test**

Run: `python -m pytest tests/test_plugin_components.py::test_expected_skills_have_skill_md_with_name_and_description -q`
Expected: PASS (both skills now exist with valid frontmatter).

- [ ] **Step 4: Commit**

```bash
git add skills/helm-chart-onboarding/
git commit -m "feat: add helm-chart-onboarding skill

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 8: Command — `/argocd-bootstrap`

**Files:**
- Create: `commands/argocd-bootstrap.md`

- [ ] **Step 1: Write `commands/argocd-bootstrap.md`**

```markdown
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
   bootstrap targets (default: the only one, or the one named `$1` context maps
   to). `$ARGUMENTS` holds an optional kube-context.
4. Render `templates/install.sh.tmpl` (from the plugin, at
   `C:/Users/hp/.claude/plugins/cache/claude-plugins-official/plugin-dev/0d82eac145a5/../argocd-gitops-plugin/templates/` — resolve via `${CLAUDE_PLUGIN_ROOT}/templates/install.sh.tmpl`)
   with: `ARGOCD_NAMESPACE`, `ARGOCD_CHART_VERSION`, `ENV_NAME`, `GITOPS_REPO_URL`.
5. Write it to `bootstrap/install.sh`, `chmod +x` it.
6. Show the user the rendered script and the exact command to run:
   `./bootstrap/install.sh [kube-context]`.
7. Do **not** run it yourself — installing Argo CD onto a cluster is the user's
   call. Offer to run it if they confirm a context.

## Output

Print: the chart version pinned, the path written, and the run command. If
`$ARGUMENTS` gave a context, include it in the example.
```

- [ ] **Step 2: Verify frontmatter parses**

Run: `python -m pytest "tests/test_plugin_components.py::test_expected_commands_present_and_named" -q`
Expected: still FAIL (4 of 5 commands missing) — but the failure message must NOT mention `argocd-bootstrap`. Confirm `argocd-bootstrap` is no longer in the missing set.

- [ ] **Step 3: Commit**

```bash
git add commands/argocd-bootstrap.md
git commit -m "feat: add /argocd-bootstrap command

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 9: Command — `/argocd-init-repo`

**Files:**
- Create: `commands/argocd-init-repo.md`

- [ ] **Step 1: Write `commands/argocd-init-repo.md`**

```markdown
---
name: argocd-init-repo
description: Scaffold a new Argo CD GitOps repo (catalog + one environment + root app + bootstrap + CLAUDE.md + CODEOWNERS), commit it, and optionally create and push the GitHub repo.
argument-hint: "<repo-name> [environment-name]"
---

Create a new Argo CD GitOps repository skeleton.

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
     (vars: `ENV_NAME`, `ARGOCD_NAMESPACE`, `GITOPS_REPO_URL`, `TARGET_REVISION`,
     `DEST_SERVER`). `GITOPS_REPO_URL` = `https://github.com/<owner>/<name>`.
   - `gitops-README.md.tmpl` → `README.md` (vars: `GITOPS_REPO_NAME`, `ENV_NAME`).
   - `gitops-CLAUDE.md.tmpl` → `.claude/CLAUDE.md` (all repo-fact vars).
   - `CODEOWNERS.tmpl` → `CODEOWNERS`.
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
```

- [ ] **Step 2: Verify frontmatter**

Run: `python -m pytest "tests/test_plugin_components.py::test_expected_commands_present_and_named" -q`
Expected: still FAIL, but `argocd-init-repo` no longer in the missing set.

- [ ] **Step 3: Commit**

```bash
git add commands/argocd-init-repo.md
git commit -m "feat: add /argocd-init-repo command

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 10: Command — `/argocd-add-chart`

**Files:**
- Create: `commands/argocd-add-chart.md`

- [ ] **Step 1: Write `commands/argocd-add-chart.md`**

```markdown
---
name: argocd-add-chart
description: Add an upstream Helm chart to the GitOps repo catalog — research it, pin an exact version, generate the wrapper Chart.yaml and a minimal values.yaml under charts/<app>/, verify with helm lint, and open a PR. Does not deploy anything.
argument-hint: "<app-name> [chart-version] [--repo <helm-repo-url>]"
---

Add a chart to `charts/<app>/` in the current GitOps repo.

## Inputs

- `$1` — app/catalog name (kebab-case, required).
- `$2` — exact chart version (optional; if omitted, pick latest stable).
- `--repo <url>` — Helm repo URL (optional; if omitted, discover via ArtifactHub).

## Preconditions

- CWD is a GitOps repo (`charts/` and `.claude/CLAUDE.md` exist).
- Working tree is clean (or ask before proceeding).

## Steps

1. Load skills `helm-chart-onboarding` and `argocd-repo-conventions`.
2. Create a branch: `git switch -c add-chart/<app>`.
3. Follow `helm-chart-onboarding` steps 1–4 to determine `CHART_NAME`,
   `CHART_VERSION` (exact), `CHART_REPO_URL`.
4. Render `${CLAUDE_PLUGIN_ROOT}/templates/Chart.yaml.tmpl` →
   `charts/<app>/Chart.yaml` and `values.yaml.tmpl` → `charts/<app>/values.yaml`.
5. Verify (must pass — do not skip):
   ```bash
   helm dependency build charts/<app>
   helm lint charts/<app>
   ```
   If a cluster is reachable also run
   `helm template charts/<app> | kubectl apply --dry-run=client -f -`.
6. Commit `charts/<app>/Chart.yaml`, `charts/<app>/values.yaml`,
   `charts/<app>/Chart.lock`. (Do not commit `charts/<app>/charts/*.tgz`.)
7. Update `.claude/CLAUDE.md` catalog inventory table; commit that too.
8. Push the branch and open a PR with `gh pr create`:
   - title: `Add <app> to catalog (<chart> <version>)`
   - body: chart source, version, why this version, and the output of
     `helm template charts/<app> | head -60` in a fenced block.
   - If `gh` is missing/unauthenticated: print the branch name and the PR body
     text, tell the user to open the PR manually. Do not fail silently.
9. Print: chart version pinned, files created, PR URL (or manual instructions).

## Notes

- Never deploy here. Deployment is `/argocd-deploy <app> <env>`.
- Never commit to the default branch directly.
```

- [ ] **Step 2: Verify frontmatter**

Run: `python -m pytest "tests/test_plugin_components.py::test_expected_commands_present_and_named" -q`
Expected: FAIL with only `argocd-deploy` and `argocd-audit` missing.

- [ ] **Step 3: Commit**

```bash
git add commands/argocd-add-chart.md
git commit -m "feat: add /argocd-add-chart command

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 11: Command — `/argocd-deploy`

**Files:**
- Create: `commands/argocd-deploy.md`

- [ ] **Step 1: Write `commands/argocd-deploy.md`**

```markdown
---
name: argocd-deploy
description: Deploy a catalog app to an environment — generate environments/<env>/apps/<app>.yaml (multi-source Argo CD Application) plus an empty per-env values overlay, verify, and open a PR.
argument-hint: "<app-name> <environment-name>"
---

Wire an existing catalog chart into an environment.

## Inputs

- `$1` — app name; must already exist at `charts/<app>/`.
- `$2` — environment name; must already exist at `environments/<env>/`.

## Preconditions

- CWD is a GitOps repo. `charts/<app>/Chart.yaml` exists. `environments/<env>/`
  exists. If either is missing, tell the user which command to run first
  (`/argocd-add-chart` or `/argocd-add-env`).
- Read `.claude/CLAUDE.md` for `GITOPS_REPO_URL`, `ARGOCD_NAMESPACE`,
  `DEST_SERVER`, and the default branch.

## Steps

1. Load skill `argocd-repo-conventions`.
2. `git switch -c deploy/<app>-<env>`.
3. Determine `TARGET_REVISION`:
   - dev-like environment (name in {`dev`, `data-platform`, `staging`} or the
     repo's single env) → the default branch.
   - `prod` / `production` → the current default-branch HEAD SHA
     (`git rev-parse origin/<branch>`), and note in the PR that this pin must be
     bumped to promote future changes.
   - Otherwise ask.
4. Ask for the destination namespace (default: `<app>`).
5. Render `${CLAUDE_PLUGIN_ROOT}/templates/application.yaml.tmpl` →
   `environments/<env>/apps/<app>.yaml` with `APP_NAME`, `ARGOCD_NAMESPACE`,
   `GITOPS_REPO_URL`, `TARGET_REVISION`, `ENV_NAME`, `NAMESPACE`, `DEST_SERVER`.
6. Create `environments/<env>/values/<app>.yaml` if absent, with content:
   ```yaml
   # Per-environment overrides for <app> in <env>. Nest under the chart name.
   ```
7. Verify:
   ```bash
   kubectl apply --dry-run=client -f environments/<env>/apps/<app>.yaml
   ```
   (If Argo CD CRDs aren't on the reachable cluster, fall back to a YAML parse
   check: `python -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" environments/<env>/apps/<app>.yaml`.)
8. Update `.claude/CLAUDE.md` deployment matrix (mark `<app>` × `<env>`). Commit.
9. Push, `gh pr create`:
   - title: `Deploy <app> to <env>`
   - body: source paths, target revision (and pin caveat for prod), destination
     namespace, and `helm template charts/<app> -f environments/<env>/values/<app>.yaml | head -60`.
   - `gh` missing → print branch + PR body, stop.
10. Print the PR URL (or manual steps) and remind the user that merge → the
    environment's root app picks it up automatically.

## Notes

- Never `kubectl apply` the Application to a live cluster from here — merging the
  PR is the deploy. Applying by hand is the user's decision.
```

- [ ] **Step 2: Verify frontmatter**

Run: `python -m pytest "tests/test_plugin_components.py::test_expected_commands_present_and_named" -q`
Expected: FAIL with only `argocd-audit` missing.

- [ ] **Step 3: Commit**

```bash
git add commands/argocd-deploy.md
git commit -m "feat: add /argocd-deploy command

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 12: Command — `/argocd-audit` + `.mcp.json`

**Files:**
- Create: `commands/argocd-audit.md`
- Create: `.mcp.json`
- Modify: `tests/test_manifest.py` (add `.mcp.json` shape tests)

- [ ] **Step 1: Write `commands/argocd-audit.md`**

```markdown
---
name: argocd-audit
description: Read-only drift report — compare the Argo CD Applications declared in environments/<env>/apps/ against what a live cluster actually has, and against each app's sync/health status. Changes nothing.
argument-hint: "[environment-name]"
---

Report drift between the GitOps repo and a live Argo CD instance.

## Inputs

- `$1` — environment to audit (optional; default: audit every `environments/*/`).

## Preconditions

- CWD is a GitOps repo.
- A reachable cluster/Argo CD. Prefer the `argocd` CLI if logged in; else
  `kubectl` against the Argo CD namespace. If neither works, run in **offline
  mode**: ask the user to paste `argocd app list -o json` (or
  `kubectl get applications -n argocd -o json`) output.
- If `mcp__argocd__*` tools are available, use them instead of shelling out.

## Steps

1. Build the **declared set**: for each `environments/<env>/apps/*.yaml`, the
   `metadata.name` and its `spec.source(s).targetRevision` + `path`.
2. Build the **live set**:
   - `argocd app list -o json` → name, `spec`, `status.sync.status`,
     `status.health.status`, `status.sync.revision`.
   - or `kubectl get applications -n <argocd-ns> -o json`.
3. Report three tables:
   - **Missing in cluster**: declared but not live → root app not synced, or
     never bootstrapped.
   - **Orphaned in cluster**: live but not declared → left over; should be
     pruned (or was created outside GitOps).
   - **Drift / unhealthy**: live and declared but `OutOfSync`, `Degraded`,
     `Missing`, or `targetRevision`/`path` differs from the repo.
4. For each row, give the one-line likely cause and the corrective command
   (e.g. `argocd app sync <name>`, "merge PR #NN", "delete `apps/<x>.yaml`").
5. Print a summary line: `<n> declared, <m> live, <k> drifted`.

## Notes

- **Read-only.** Never `sync`, `apply`, `delete`, or edit anything. Offer to
  generate the fix PR via `/argocd-deploy` but do not act.
- This replaces the hand-written `applications.txt` reconcile loop.
```

- [ ] **Step 2: Write `.mcp.json`**

```json
{
  "mcpServers": {
    "argocd": {
      "_comment": "OPTIONAL. Akuity's Argo CD MCP server. Disabled by default — the plugin's commands and agents work fully with the argocd/kubectl CLIs. Enable only for deep interactive troubleshooting: remove the leading underscore from _disabled, set ARGOCD_BASE_URL and ARGOCD_API_TOKEN, then restart Claude Code. See README.md > Optional: Argo CD MCP.",
      "_disabled": true,
      "command": "npx",
      "args": ["-y", "argocd-mcp@latest", "stdio"],
      "env": {
        "ARGOCD_BASE_URL": "${ARGOCD_BASE_URL}",
        "ARGOCD_API_TOKEN": "${ARGOCD_API_TOKEN}"
      }
    }
  }
}
```

- [ ] **Step 3: Add `.mcp.json` tests to `tests/test_manifest.py`**

Append:

```python
def test_mcp_json_is_valid_and_argocd_disabled_by_default():
    data = load(".mcp.json")
    assert "argocd" in data["mcpServers"]
    srv = data["mcpServers"]["argocd"]
    # Disabled by default: our convention is the _disabled marker key set true.
    assert srv.get("_disabled") is True
    # No secrets inlined — only ${ENV} references.
    for v in srv.get("env", {}).values():
        assert v.startswith("${") and v.endswith("}")
```

- [ ] **Step 4: Run the manifest + component tests**

Run: `python -m pytest tests/test_manifest.py tests/test_plugin_components.py -q`
Expected: `test_manifest.py` — 6 passed. `test_plugin_components.py` — all pass now that all 5 commands exist (`test_expected_commands_present_and_named`, `test_no_hardcoded_home_paths_in_components`, agents test still fails → Task 13).

Wait: the agents test (`test_expected_agents_present_with_description`) will error because `agents/` doesn't exist yet. Expected: that one test FAILS, everything else PASSES.

- [ ] **Step 5: Commit**

```bash
git add commands/argocd-audit.md .mcp.json tests/test_manifest.py
git commit -m "feat: add /argocd-audit command and optional argocd MCP config

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 13: Agent — `argocd-onboarder`

**Files:**
- Create: `agents/argocd-onboarder.md`

- [ ] **Step 1: Write `agents/argocd-onboarder.md`**

```markdown
---
name: argocd-onboarder
description: >-
  Use to onboard a brand-new application end-to-end into an Argo CD GitOps repo:
  research the upstream Helm chart, scaffold the catalog wrapper, deploy it to a
  named environment, and open the PR — all in one delegated run. Trigger when the
  user says "onboard <app>", "add <app> and deploy it to <env>", or "get <app>
  running on <env>". Do NOT use for changes to an already-onboarded app.
tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch
---

You onboard one application into the Argo CD GitOps repo in the current working
directory, from nothing to an open PR.

## Operating rules

- Load the plugin skills `helm-chart-onboarding` and `argocd-repo-conventions`
  before writing anything. Follow them exactly.
- CLI-first: use `helm`, `kubectl`, `git`, `gh`. If `mcp__argocd__*` tools exist,
  you may use them for read-only checks; never for writes.
- One branch for the whole onboarding: `onboard/<app>-<env>`.
- Never deploy to a live cluster. Never commit to the default branch. Never
  force-push. Opening the PR with `gh` is the only outward action, and only after
  the local verification below passes.
- If a required input is ambiguous (chart repo, version, destination namespace,
  which environment), stop and ask — do not guess.

## Sequence

1. Confirm CWD is a GitOps repo (`charts/`, `environments/`, `.claude/CLAUDE.md`).
   If not, stop and report.
2. Resolve chart: name, exact version, Helm repo URL (ArtifactHub via WebFetch if
   needed). Prefer official repos.
3. `git switch -c onboard/<app>-<env>`.
4. Scaffold catalog: render `Chart.yaml.tmpl` + `values.yaml.tmpl` into
   `charts/<app>/`. Pull upstream values, add only the minimal overrides needed
   for a first healthy deploy (resources, persistence, ingress off unless asked).
5. Verify catalog: `helm dependency build charts/<app>` → `helm lint charts/<app>`
   → (if cluster reachable) `helm template charts/<app> | kubectl apply
   --dry-run=client -f -`. All must pass; fix and re-run until they do.
6. Deploy wiring: render `application.yaml.tmpl` into
   `environments/<env>/apps/<app>.yaml`; create
   `environments/<env>/values/<app>.yaml` (comment-only). Use the dev/prod
   `targetRevision` rule from `argocd-repo-conventions`.
7. Verify manifest: `kubectl apply --dry-run=client -f environments/<env>/apps/<app>.yaml`
   (or YAML parse fallback).
8. Update `.claude/CLAUDE.md`: catalog inventory row + deployment matrix cell.
9. Commit in logical chunks (catalog, deploy wiring, docs), each with the
   `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer.
10. Push; `gh pr create` titled `Onboard <app> → <env>` with a body covering:
    chart + version + why, the `helm template ... | head -80` preview, target
    revision (+ prod pin caveat), destination namespace, and post-merge note
    ("the <env> root app syncs this automatically").
11. Report back: files created, verification results (paste the `helm lint` and
    dry-run output), and the PR URL. If `gh` is unavailable, report the branch
    name and the full PR body text for the user to open manually.

## Failure handling

If any verification step fails and you cannot fix it in three attempts, stop.
Report what failed, the exact command and output, and your best hypothesis. Do
not open a PR for a chart that does not lint or template cleanly.
```

- [ ] **Step 2: Run the full component test file**

Run: `python -m pytest tests/test_plugin_components.py -q`
Expected: PASS — all commands, both skills, the agent present; no hardcoded home paths.

- [ ] **Step 3: Commit**

```bash
git add agents/argocd-onboarder.md
git commit -m "feat: add argocd-onboarder agent

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 14: README + test-suite runner + pytest config

**Files:**
- Create: `README.md`
- Create: `tests/README.md`
- Create: `pytest.ini`
- Create: `tests/smoke/helm_smoke.sh`
- Create: `tests/smoke/argocd_e2e.sh`

- [ ] **Step 1: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -q
```

- [ ] **Step 2: Write `README.md`**

````markdown
# argocd-gitops-plugin

A Claude Code plugin for running applications on Argo CD with GitOps. It
scaffolds and operates a repo with a **catalog** of Helm wrapper charts and one
folder per **environment**, wired together with the app-of-apps pattern.

## What it does (Phase 1)

| Command | Purpose |
|---------|---------|
| `/argocd-init-repo <name> [env]` | Scaffold a new GitOps repo and (optionally) create + push the GitHub repo. |
| `/argocd-bootstrap [kube-context]` | Generate `bootstrap/install.sh` — installs Argo CD and applies the root app. |
| `/argocd-add-chart <app> [version]` | Research an upstream Helm chart, pin it, scaffold `charts/<app>/`, open a PR. |
| `/argocd-deploy <app> <env>` | Wire a catalog app into an environment (`Application` + values overlay), open a PR. |
| `/argocd-audit [env]` | Read-only drift report: repo vs live Argo CD. |

Plus the `argocd-onboarder` agent, which does add-chart → deploy → PR in one run.

## Requirements

Install and put on `PATH`:

- `git`
- `gh` (GitHub CLI) — authenticated (`gh auth login`). Needed for repo creation
  and PRs. Without it, commands print manual instructions instead of failing.
- `helm` v3.8+
- `kubectl`
- `argocd` CLI — only for `/argocd-audit` against a live instance.

A reachable Kubernetes cluster is needed only for bootstrap and audit, not for
scaffolding.

## Install

```bash
# from a marketplace clone or local path
/plugin marketplace add OmalCooray/argocd-gitops-plugin
/plugin install argocd-gitops-plugin
```

Or point Claude Code at a local checkout during development.

## Typical flow

```
/argocd-init-repo data-platform-k8s-configs data-platform
cd data-platform-k8s-configs
/argocd-bootstrap docker-desktop        # then run ./bootstrap/install.sh
/argocd-add-chart podinfo               # review + merge the PR
/argocd-deploy podinfo data-platform    # review + merge the PR
/argocd-audit data-platform
```

## Optional: Argo CD MCP

`.mcp.json` ships a disabled entry for
[Akuity's Argo CD MCP server](https://github.com/akuity/argocd-mcp). The plugin
does not need it. To enable: remove `"_disabled": true`, set `ARGOCD_BASE_URL`
and `ARGOCD_API_TOKEN` in your environment, restart Claude Code. Useful for
richer interactive troubleshooting once the Phase 2 doctor agent lands.

## Design & roadmap

See `docs/superpowers/specs/2026-09-10-argocd-gitops-plugin-design.md`.
Phase 2: `values-review`, `/argocd-doctor`. Phase 3: `/argocd-add-env`,
`/argocd-promote`, secrets.

## Development

```bash
python -m pytest        # structural + template tests (no cluster needed)
bash tests/smoke/helm_smoke.sh     # renders a wrapper chart, helm lint/template
bash tests/smoke/argocd_e2e.sh     # installs Argo CD on the current context (destructive-ish)
```
````

- [ ] **Step 3: Write `tests/README.md`**

```markdown
# Tests

| File | Needs | Checks |
|------|-------|--------|
| `test_manifest.py` | python | `plugin.json` + `.mcp.json` shape |
| `test_templates.py` | python | templates render to golden files; no stray placeholders |
| `test_plugin_components.py` | python | commands/skills/agents exist with valid frontmatter; no hardcoded home paths |
| `smoke/helm_smoke.sh` | helm, network | render wrapper chart from templates → `helm dependency build` + `helm lint` |
| `smoke/argocd_e2e.sh` | kubectl, helm, a throwaway cluster | install Argo CD, apply a root app, confirm it reconciles |

Run the fast suite with `python -m pytest`. Smoke scripts are opt-in.
```

- [ ] **Step 4: Write `tests/smoke/helm_smoke.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/tests/.out/smoke-podinfo"
rm -rf "$OUT"; mkdir -p "$OUT"

python "$ROOT/tests/render.py" "$ROOT/templates/Chart.yaml.tmpl" \
  "$ROOT/tests/fixtures/podinfo.vars.json" > "$OUT/Chart.yaml"
python "$ROOT/tests/render.py" "$ROOT/templates/values.yaml.tmpl" \
  "$ROOT/tests/fixtures/podinfo.vars.json" > "$OUT/values.yaml"

helm dependency build "$OUT"
helm lint "$OUT"
helm template "$OUT" >/dev/null
echo "OK: wrapper chart builds, lints, and templates"
```

- [ ] **Step 5: Write `tests/smoke/argocd_e2e.sh`**

```bash
#!/usr/bin/env bash
# End-to-end: install Argo CD on the CURRENT kube-context, apply a root app that
# points at a scratch GitOps repo, and confirm the child app reconciles.
# Intended for a throwaway cluster (docker-desktop, kind). Not idempotent-clean.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NS=argocd
CTX="$(kubectl config current-context)"
echo ">> context: $CTX  (Ctrl-C now if that is not a throwaway cluster)"
sleep 5

helm repo add argo https://argoproj.github.io/argo-helm >/dev/null 2>&1 || true
helm repo update argo >/dev/null
helm upgrade --install argo-cd argo/argo-cd -n "$NS" --create-namespace --wait

kubectl wait --for=condition=Established \
  crd/applications.argoproj.io crd/appprojects.argoproj.io --timeout=120s

# Minimal in-line root app pointing at the public podinfo repo's kustomize sample,
# proving app-of-apps reconciliation works.
kubectl apply -n "$NS" -f - <<'YAML'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: e2e-podinfo
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/stefanprodan/podinfo
    targetRevision: master
    path: kustomize
  destination:
    server: https://kubernetes.default.svc
    namespace: e2e-podinfo
  syncPolicy:
    automated: { prune: true, selfHeal: true }
    syncOptions: [CreateNamespace=true]
YAML

echo ">> waiting for e2e-podinfo to become Healthy/Synced (up to 3m)"
for i in $(seq 1 36); do
  sync=$(kubectl get app e2e-podinfo -n "$NS" -o jsonpath='{.status.sync.status}' 2>/dev/null || true)
  health=$(kubectl get app e2e-podinfo -n "$NS" -o jsonpath='{.status.health.status}' 2>/dev/null || true)
  echo "   [$i] sync=$sync health=$health"
  [ "$sync" = "Synced" ] && [ "$health" = "Healthy" ] && { echo "OK"; exit 0; }
  sleep 5
done
echo "FAIL: e2e-podinfo did not converge"; exit 1
```

- [ ] **Step 6: `chmod +x` the scripts and run the fast suite**

Run:
```bash
chmod +x tests/smoke/*.sh
python -m pytest
```
Expected: all tests pass (manifest 6, templates 11, components 4). Total green.

- [ ] **Step 7: Run the helm smoke test**

Run: `bash tests/smoke/helm_smoke.sh`
Expected: ends with `OK: wrapper chart builds, lints, and templates`.
(Requires network to `stefanprodan.github.io`. If the pinned `podinfo` version 404s, bump it in `tests/fixtures/podinfo.vars.json` and golden `Chart.yaml` per Task 4 Step 13.)

- [ ] **Step 8: Commit**

```bash
git add README.md tests/README.md pytest.ini tests/smoke/
git commit -m "docs: add README and smoke tests

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 15: End-to-end dry run of the plugin's own workflow

This task exercises the plugin the way a user would, on the local `docker-desktop`
cluster, and fixes whatever breaks. No new source files — it produces a
throwaway repo under `tests/.out/` and (optionally) installs Argo CD.

**Files:**
- Modify: any template / skill / command file that the run reveals to be wrong.

- [ ] **Step 1: Scaffold a scratch GitOps repo by hand-following `/argocd-init-repo`**

Do exactly what `commands/argocd-init-repo.md` says, targeting
`tests/.out/e2e-repo`, env `data-platform`, owner `OmalCooray`, namespace
`argocd`, branch `master`, **no** GitHub push. Render every template with the
plugin's own `tests/render.py`.

Expected: a repo tree matching `skills/argocd-repo-conventions/reference/repo-layout.md`.
Verify: `python -c "import yaml; yaml.safe_load(open('tests/.out/e2e-repo/environments/data-platform/root.yaml'))"` — no error.

- [ ] **Step 2: Follow `/argocd-add-chart podinfo` against the scratch repo**

From `tests/.out/e2e-repo`, follow `commands/argocd-add-chart.md`: branch,
resolve `podinfo` (repo `https://stefanprodan.github.io/podinfo`, latest stable),
render the wrapper, `helm dependency build`, `helm lint`.

Expected: `helm lint` → `0 chart(s) failed`. Commit on the branch.

- [ ] **Step 3: Follow `/argocd-deploy podinfo data-platform`**

Render `application.yaml.tmpl` into
`environments/data-platform/apps/podinfo.yaml`, create the comment-only overlay,
`kubectl apply --dry-run=client -f environments/data-platform/apps/podinfo.yaml`.

Expected: dry-run succeeds if Argo CD CRDs are present; otherwise YAML parse
check passes. Fix the template if there is a real schema/parse error.

- [ ] **Step 4: Optional full e2e — install Argo CD and reconcile**

If the user confirms `docker-desktop` is disposable, run:
```bash
bash tests/smoke/argocd_e2e.sh
```
Then also apply the scratch repo's real root app after pushing the scratch repo
somewhere Argo CD can read (or point `repoURL` at a local path via `file://` is
not supported — skip if no push target). At minimum, `argocd_e2e.sh` proves
app-of-apps reconciliation on this cluster.

Expected: `argocd_e2e.sh` prints `OK`.

- [ ] **Step 5: Record findings and fix**

For every deviation found (template field Argo CD rejected, skill instruction
that was ambiguous, command step that referenced a missing var), fix the
underlying file. Re-run the affected `pytest` tests and the relevant smoke script.

- [ ] **Step 6: Clean up and commit any fixes**

```bash
rm -rf tests/.out
git add -A
git commit -m "fix: corrections from end-to-end dry run

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
(If nothing needed fixing, skip the commit and note "e2e clean" in the task
report.)

---

## Task 16: Validate the plugin and finalise

**Files:**
- Modify: `.claude-plugin/plugin.json` (bump to `0.1.0` → keep; add `homepage` if desired)
- Create: `docs/superpowers/plans/2026-09-10-argocd-gitops-plugin-phase1.md` (this file — already exists)

- [ ] **Step 1: Run the plugin-validator agent**

Dispatch the `plugin-dev:plugin-validator` agent against `C:\claude\argocd-gitops-plugin`.
Expected: reports the manifest valid, all components discoverable, no path issues.
Fix anything it flags (frontmatter typos, missing `description`, etc.).

- [ ] **Step 2: Run the skill-reviewer agent on both skills**

Dispatch `plugin-dev:skill-reviewer` for `skills/argocd-repo-conventions` and
`skills/helm-chart-onboarding`.
Expected: descriptions score well for triggering; body follows progressive
disclosure. Apply reasonable suggestions.

- [ ] **Step 3: Full green test run**

Run: `python -m pytest`
Expected: all pass.

Run: `bash tests/smoke/helm_smoke.sh`
Expected: `OK: wrapper chart builds, lints, and templates`.

- [ ] **Step 4: Final commit + tag**

```bash
git add -A
git commit -m "chore: finalize Phase 1 of argocd-gitops-plugin

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>" || echo "nothing to commit"
git tag -a v0.1.0 -m "Phase 1: scaffold, catalog, deploy, bootstrap, audit, onboarder"
git log --oneline
```

- [ ] **Step 5: Report**

Summarise: components built, test results (paste `pytest` summary + smoke
output), and the two follow-up phases from the spec. State plainly whether the
optional cluster e2e was run or skipped.

---

## Self-Review

**1. Spec coverage**

| Spec item (Phase 1) | Task |
|---|---|
| Plugin scaffold (`plugin.json`, README, `templates/`) | 2, 4, 14 |
| `templates/` — Chart.yaml, application.yaml, root.yaml, install.sh | 4 |
| Skill `argocd-repo-conventions` | 6 |
| Skill `helm-chart-onboarding` | 7 |
| `/argocd-init-repo` | 9 |
| `/argocd-add-chart` | 10 |
| `/argocd-deploy` | 11 |
| `/argocd-bootstrap` | 8 |
| `/argocd-audit` | 12 |
| Agent `argocd-onboarder` | 13 |
| `.mcp.json` with Argo CD MCP defined-but-disabled | 12 |
| Git branch + PR flow via `gh` | 9, 10, 11, 13 (each command's steps) |
| Catalog vs environments layout; multi-source `$values` | 4, 6 |
| dev tracks branch / prod tracks pinned SHA | 6, 11, 13 |
| CODEOWNERS on prod path | 4 (template), 9 (rendered) |
| Migration note (existing repo → new layout) | covered in spec; `/argocd-init-repo` + manual `git mv`; not a Phase 1 automated task (out of scope, documented) |
| Exit criterion: init → bootstrap → add-chart → deploy → chart on cluster | 15 (e2e dry run) |

Gaps: the spec's "migrate the existing `data-platform-k8s-configs`" is intentionally not an automated Phase 1 task — flagged in the spec's Non-Goals/assumptions as a one-time manual `git mv` guided by the conventions skill. No code task needed.

**2. Placeholder scan** — no "TBD"/"handle appropriately"/"similar to Task N". Every command file, skill, template, and test is shown in full.

**3. Type consistency**

- Template variable names are identical across `render.py`, `podinfo.vars.json`,
  every `*.tmpl`, the golden files, and each command's "render X with vars ..."
  step: `APP_NAME, CHART_NAME, CHART_VERSION, CHART_REPO_URL, NAMESPACE,
  ENV_NAME, GITOPS_REPO_URL, GITOPS_REPO_NAME, TARGET_REVISION, ARGOCD_NAMESPACE,
  ARGOCD_CHART_VERSION, DEST_SERVER`.
- `render()` / `placeholders()` signatures in `tests/render.py` match their use
  in `tests/test_templates.py`.
- Command `name:` frontmatter values match the file stems and `EXPECTED_COMMANDS`
  in `tests/test_plugin_components.py`: `argocd-bootstrap, argocd-init-repo,
  argocd-add-chart, argocd-deploy, argocd-audit`.
- Skill dir names match `EXPECTED_SKILLS`; agent file stem matches
  `EXPECTED_AGENTS`.
- `.mcp.json` disabled marker (`_disabled: true`) is asserted with the same key
  in `test_manifest.py`.

Fixed during review: Task 12 Step 4 note clarifies the agents test is expected to
be the only failure at that point (agents dir arrives in Task 13).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-10-argocd-gitops-plugin-phase1.md`.
