# argocd-gitops-plugin — Custom Manifests in Wrapper Charts

**Date:** 2026-09-10
**Status:** Approved (design phase)
**Author:** Omal Cooray (with Claude)

## Summary

Add a first-class, **opt-in** capability to the `argocd-gitops-plugin` for placing
your own templated Kubernetes manifests alongside a pinned public Helm chart —
without editing or vendoring the upstream chart. Examples: a `ServiceMonitor` for
an app whose chart has no monitoring support, a Traefik `IngressRoute`, a
`NetworkPolicy`, a `PrometheusRule`. The mechanism is general; the plugin ships a
small library of correct-by-construction starters plus a generic authoring path.

This is spec **#1 of 2**. Spec #2 (`argocd-observability` / `/argocd-observe`)
builds the full "onboard app X into observability" workflow — ServiceMonitor +
Grafana dashboard + alerts + rich verification — on top of this primitive, and
has its own brainstorm → spec → plan.

**Acceptance target for the combined effort (both specs):** live Grafana
dashboards for `airflow`, `metabase`, `trino`, `mysql`, and the Kubernetes
cluster, running against the `test-k8s-configs` repo on the local cluster, with
the plugin updated whenever a gap surfaces.

## Background

The plugin's central artifact is a **wrapper chart**: `charts/<app>/Chart.yaml`
declares the upstream chart as a pinned dependency, `charts/<app>/values.yaml`
holds overrides nested under the subchart name, and `charts/<app>/charts/` (the
downloaded `.tgz`) is git-ignored. Argo CD's repo-server runs `helm dependency
build` + `helm template` on the wrapper at sync time.

A wrapper chart is itself a real Helm chart, so it can carry its own
`templates/` directory. Helm renders those templates **alongside** every template
from the dependency `.tgz` into one manifest stream. The upstream chart stays a
sealed, pinned dependency — you add sibling templates to *your* wrapper.

This was done ad hoc during the Airflow/Metabase/Trino end-to-end run
(`charts/trino/templates/worker-pdb.yaml`) but is undocumented and unsupported.
Public charts routinely lack resources a platform needs — ServiceMonitors,
IngressRoutes, NetworkPolicies, PDBs — and the recurring need is open-ended.

## Goals

- Document `charts/<app>/templates/` as a supported place for your own manifests.
- A command, `/argocd-add-manifest <app> <kind>`, that scaffolds a correct wrapper
  template (from a starter library) or authors one from a free-text description.
- Starters for the common kinds: `ServiceMonitor`, `PodMonitor`, Traefik
  `IngressRoute`, Gateway API `HTTPRoute`, plain `Ingress`, `NetworkPolicy`,
  `PrometheusRule`.
- A skill (`argocd-extra-manifests`) holding the mechanism, conventions, the
  starter library, and reference material (Prometheus-Operator label rules,
  Traefik IngressRoute, Argo CD hooks vs sync-waves).
- Every added manifest is gated on a values flag, verified to render and to be
  accepted by its CRD, and reachable per-environment via the existing `$values`
  overlay.

## Non-Goals

- **Not** auto-adding any manifest. `/argocd-add-chart` and `/argocd-deploy`
  never touch `templates/`. Extras are added only by an explicit
  `/argocd-add-manifest` (or an explicit ask).
- Not the observability workflow (dashboards, alert rules as a bundle, rich
  metric verification) — that is spec #2.
- Not own-application chart authoring (a `frontend`/`backend` chart you develop).
- Not the registry-chart source type (`chart:` + `targetRevision:` instead of
  `path:`) — deferred.

## Design

### The convention (documented in `argocd-repo-conventions`)

A wrapper chart may carry your own manifests in `charts/<app>/templates/`. Rules:

- **One file per resource kind**, kebab-named: `templates/servicemonitor.yaml`,
  `templates/ingressroute.yaml`.
- **Mandatory: the wrapper's base `values.yaml` sets `<chart>.fullnameOverride:
  <app>`** so every upstream-generated name is a predictable `<app>-<component>`
  that your templates can target by name. A parent chart cannot call a
  subchart's `_helpers.tpl`, so this naming contract is how added templates
  reference chart-generated Services / pods / labels.
- **Every added manifest is gated on a values flag** —
  `{{- if .Values.serviceMonitor.enabled }}` — with a sensible default (monitors
  on, routes off) overridable per environment through the `$values` overlay.
- **A resource lives with whatever it is *about*.** An app's route/monitor →
  `charts/<app>/`. A shared Traefik middleware every app uses →
  `charts/traefik/`. Cluster-wide alert rules / Alertmanager config →
  `charts/kube-prometheus-stack/` (values or `templates/`).
- **CRD-exists is a sync-wave concern, not a co-location one.** The
  controller/operator app (`traefik`, `kube-prometheus-stack`) must sit at a
  lower `argocd.argoproj.io/sync-wave` than apps that ship its custom resources.
  Record the wave numbers in the environment's `.claude/CLAUDE.md`.
- **Template context available:** `.Values` (including `.Values.<chart>.*`),
  `.Release.Name`, `.Release.Namespace`, the wrapper's `.Chart`, `.Capabilities`,
  `.Values.global.*`. **Not available:** the upstream chart's `_helpers.tpl`.
- **A `templates/` change is a chart change** — bump `charts/<app>/Chart.yaml`
  `version`.

### New skill: `argocd-extra-manifests`

```
skills/argocd-extra-manifests/
├── SKILL.md
└── references/
    ├── starters/
    │   ├── servicemonitor.yaml
    │   ├── podmonitor.yaml
    │   ├── ingressroute.yaml
    │   ├── httproute.yaml
    │   ├── ingress.yaml
    │   ├── networkpolicy.yaml
    │   └── prometheusrule.yaml
    ├── prometheus-operator.md
    ├── traefik-ingressroute.md
    └── hooks-and-waves.md
```

**`SKILL.md`** — description triggers on "add a ServiceMonitor / PodMonitor /
IngressRoute / NetworkPolicy / custom manifest / extra template to a chart",
"the chart has no monitoring / ingress support". Body:

- The mechanism: wrapper `templates/` renders alongside the pinned dependency;
  you never touch the upstream chart.
- The convention rules above (naming contract, values gate, co-location,
  sync-wave, visible context).
- Authoring checklist:
  1. Ensure `<chart>.fullnameOverride: <app>` is in the wrapper's base values;
     add it if missing.
  2. `helm template charts/<app>` once to read the real Service names, **named**
     ports, and pod labels the new manifest must target.
  3. Start from `references/starters/<kind>.yaml` if one fits; else author per
     this checklist.
  4. Gate on a new `values.yaml` stanza; wire per-env overrides through
     `$values`.
  5. Never `include` a subchart `_helpers` template.
  6. Verify: `helm template charts/<app>` renders; if a cluster with the CRD is
     reachable, `helm template charts/<app> | kubectl apply --dry-run=server -f -`.
  7. Bump `charts/<app>/Chart.yaml` `version`.
- Pointer to `prometheus-operator.md`, `traefik-ingressroute.md`,
  `hooks-and-waves.md`.

**`references/starters/*.yaml`** — each is a real wrapper-chart template, not
pseudo-code:
- Opens with `{{- if .Values.<key>.enabled }}` … closes with `{{- end }}`.
- Targets `<app>-<component>` names and **named** ports via values with sane
  defaults.
- Carries a top comment: what it is, which CRD/controller it needs, which values
  keys it reads.
- `servicemonitor.yaml` / `podmonitor.yaml`: `metadata.labels` that a default
  kube-prometheus-stack (with `serviceMonitorSelectorNilUsesHelmValues: false`)
  picks up; a note that a stricter install needs `release: <kps-release>`.
  `endpoints[].port` / `podMetricsEndpoints[].port` is a **named** port. Reads
  `path` (default `/metrics`), `scheme` (default `http`), `interval` (default
  `30s`), `scrapeTimeout`.
- `ingressroute.yaml` (Traefik): reads `host`, `entryPoints` (default
  `[websecure]`), `service`/`port`, optional `middlewares`, TLS via `certResolver`
  or a `secretName`.
- `httproute.yaml` (Gateway API): reads `parentRef` (gateway name/namespace),
  `hostnames`, `backendRef`.
- `ingress.yaml`: `ingressClassName`, `host`, `path`/`pathType`, TLS `secretName`,
  `annotations`.
- `networkpolicy.yaml`: a default-deny-ingress + allow-from-namespace starter,
  `podSelector` on `<app>` labels, configurable `ingress`/`egress` rules.
- `prometheusrule.yaml`: a `spec.groups` skeleton with one example recording and
  one alerting rule referencing the app's metrics.

**`references/prometheus-operator.md`** — the `serviceMonitorSelector` /
`podMonitorSelector` / `ruleSelector` label-matching rules and the
`…NilUsesHelmValues` flag; named-port requirement; `path`/`scheme`/`interval`
defaults; `relabelings`/`metricRelabelings` basics; how to confirm a target is
scraped (`/api/v1/targets`, `/api/v1/query`).

**`references/traefik-ingressroute.md`** — `entryPoints`, `routes[].match`
syntax, `kind: Rule`, service references and `port`, `Middleware` refs, TLS
(`certResolver` vs a `Secret`), and that the `IngressRoute` CRD comes from the
traefik chart.

**`references/hooks-and-waves.md`** — sync-waves first (order within one sync;
resources stay normal — visible, health-tracked, pruned). Hooks only for a
transient lifecycle-bound task (`PreSync` migration/backup, `Sync` job with
hook-delete semantics, `PostSync` smoke test / notification, `SyncFail`
cleanup). Traps, each seen in the earlier e2e:
1. **PostSync deadlock** — main workloads must not wait on what a PostSync hook
   produces. Rule: a PreSync/Sync hook may unblock main resources; a PostSync
   hook only depends on them.
2. Helm hooks are translated (`pre-install,pre-upgrade` → `PreSync`;
   `post-install,post-upgrade` → `PostSync`); a chart's `post-install` migration
   job can deadlock — fix with `useHelmHooks: false` + `argocd.argoproj.io/hook:
   Sync`.
3. `hook-delete-policy` — default `BeforeHookCreation` keeps the last run for
   logs; `HookSucceeded` deletes immediately.
4. `prune: false` + hooks — leftover hook RBAC/ServiceAccounts show as
   "requiresPruning" noise.
The starters here are plain resources + a sync-wave when they need a CRD — no
hooks. Hooks enter only if a *Job* manifest is added.

### New command: `/argocd-add-manifest`

```
/argocd-add-manifest <app> <kind> [--env <env>]
```

- `<kind>` — a starter name (`servicemonitor`, `podmonitor`, `ingressroute`,
  `httproute`, `ingress`, `networkpolicy`, `prometheusrule`) **or** free text
  ("a CronJob that runs pg_dump nightly").
- **Follows the interaction contract** (`references/interaction-style.md`):
  announce each step, show commands + key output, checkpoint before `git push` /
  the PR.
- **Preconditions:** CWD is a GitOps repo; `charts/<app>/Chart.yaml` exists.
- **Steps:**
  1. Load `argocd-extra-manifests` and `argocd-repo-conventions`.
  2. Confirm `charts/<app>/values.yaml` sets `<chart>.fullnameOverride: <app>`;
     add it if missing (note the change — it can shift resource names on next
     sync, so call it out).
  3. `helm template charts/<app>` once to read the real Service names, named
     ports, and pod labels the manifest must target.
  4. Starter path: copy `references/starters/<kind>.yaml` →
     `charts/<app>/templates/<kind>.yaml`; adapt names/ports/paths; add the
     gating values stanza to `charts/<app>/values.yaml`. Free-text path: author
     from the skill's checklist.
  5. If the kind needs a CRD (ServiceMonitor / PodMonitor / IngressRoute /
     HTTPRoute / PrometheusRule): check the controller app exists in
     `environments/*/apps/` and its sync-wave is lower than `<app>`'s. If not,
     report that and stop before committing.
  6. Verify: `helm template charts/<app>` renders; if a cluster with the CRD is
     reachable, `helm template charts/<app> | kubectl apply --dry-run=server`.
  7. Bump `charts/<app>/Chart.yaml` `version`.
  8. Checkpoint → commit on a branch `add-manifest/<app>-<kind>` → PR.
  9. Suggest `/argocd-sync <app> <env>` to roll it out; for a ServiceMonitor,
     name the functional check ("target appears in Prometheus
     `/api/v1/targets`").

### Edits to existing components

- **`skills/argocd-repo-conventions/SKILL.md`** — add a short "Custom manifests"
  section: wrapper charts may carry `templates/`; the `fullnameOverride` rule is
  now mandatory; see `argocd-extra-manifests` for how.
- **`commands/argocd-add-chart.md`** / **`commands/argocd-deploy.md`** — one line
  each: "never adds `charts/<app>/templates/`; use `/argocd-add-manifest`".
- **`skills/argocd-rollout/SKILL.md`** — functional-check table gets a row: "extra
  manifest (ServiceMonitor / IngressRoute / …)" → verify it renders, the CRD
  accepts it, and it does its job (a monitor's target is `up` in Prometheus; a
  route resolves).
- **`README.md`** — command table + roadmap (note spec #2 to come).

## Testing

- **`tests/test_plugin_components.py`** — add `argocd-add-manifest` to
  `EXPECTED_COMMANDS`, `argocd-extra-manifests` to `EXPECTED_SKILLS`.
- **`tests/test_starters.py`** (new) — for each `references/starters/*.yaml`:
  render with `tests/render.py` against a fixture values set, then
  `yaml.safe_load`; `kind` matches the filename; the file opens with a
  `{{- if .Values.<x>.enabled` gate; forbidden pattern — no
  `include "<something>.` referencing a subchart helper.
- **`tests/smoke/extra_manifest_smoke.sh`** (new) — scaffold a `podinfo` wrapper
  chart, drop in the `servicemonitor` starter, `helm dependency build` + `helm
  template`, assert the `ServiceMonitor` renders with `matchLabels` targeting the
  app and a named port. If a cluster with the Prometheus-Operator CRDs is
  reachable, also `kubectl apply --dry-run=server`.

## File structure

```
argocd-gitops-plugin/
├── commands/
│   ├── argocd-add-manifest.md              # NEW
│   ├── argocd-add-chart.md                 # EDIT (one line)
│   └── argocd-deploy.md                    # EDIT (one line)
├── skills/
│   ├── argocd-extra-manifests/             # NEW
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── starters/{servicemonitor,podmonitor,ingressroute,httproute,ingress,networkpolicy,prometheusrule}.yaml
│   │       ├── prometheus-operator.md
│   │       ├── traefik-ingressroute.md
│   │       └── hooks-and-waves.md
│   ├── argocd-repo-conventions/SKILL.md    # EDIT
│   └── argocd-rollout/SKILL.md             # EDIT
├── tests/
│   ├── test_plugin_components.py           # EDIT
│   ├── test_starters.py                    # NEW
│   └── smoke/extra_manifest_smoke.sh       # NEW
├── README.md                               # EDIT
└── docs/superpowers/specs/2026-09-10-argocd-extra-manifests-design.md   # this file
```

## Risks

- **Name-matching drift** — an added template targets `<app>-scheduler`; a chart
  upgrade renames it. Mitigation: the `fullnameOverride` rule makes names
  stable across upgrades for most charts; `/argocd-sync`'s functional check
  catches a monitor that stops scraping.
- **Starter rot** — CRD schemas (ServiceMonitor, IngressRoute) evolve.
  Mitigation: `test_starters.py` renders + parses them; the schemas are stable
  in practice; starters carry a "verified against" version comment.
- **CRD ordering** — an IngressRoute synced before Traefik installs its CRD
  fails. Mitigation: step 5 checks the controller app + sync-wave before
  committing.
