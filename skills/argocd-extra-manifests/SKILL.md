---
name: argocd-extra-manifests
description: Add your own templated Kubernetes manifests (ServiceMonitor, PodMonitor, IngressRoute, NetworkPolicy, extra RBAC, a CronJob…) to a wrapper chart's templates/ directory, alongside a pinned upstream Helm chart, without editing or vendoring the upstream. Load when a public chart lacks a resource your platform needs and you want to add it as a first-class part of the wrapper.
---

# Extra manifests in a wrapper chart

## Mechanism

A wrapper chart (`charts/<app>/`) is itself a real Helm chart. It can carry its
own `templates/` directory. Helm — and Argo CD's repo-server — renders those
templates **alongside** every template from the pinned dependency `.tgz`, into
one manifest stream. You never touch, unpack, or fork the upstream chart; you add
sibling templates to *your* wrapper.

```
charts/<app>/
├── Chart.yaml        # dependency: <upstream> pinned
├── values.yaml       # overrides under <upstream>:  +  your own top-level keys
├── charts/           # git-ignored: the downloaded <upstream>-x.y.z.tgz
└── templates/        # YOUR manifests — one file per kind
    └── servicemonitor.yaml
```

## Conventions

- **One file per resource kind**, kebab-named (`templates/servicemonitor.yaml`).
- **Your templates must be able to name chart-generated resources.** Helm's
  named templates share one global namespace, so `{{ include "<upstream>.fullname" . }}`
  from the wrapper *does* resolve — but it executes against the **wrapper's**
  context and values (it reads the wrapper's top-level `.Values.fullnameOverride`,
  not `.Values.<chart>.fullnameOverride`), so it silently computes the **wrong**
  name, and subchart-name collisions resolve unpredictably. So never `include` a
  subchart's named templates — reference chart-generated resources by their
  rendered name instead. Two ways that name becomes predictable:
  1. **Argo CD sets the Helm release name to the Application name** (`<app>`).
     Some charts derive names from the release name and then produce
     `<app>-<component>` in-cluster with no configuration; others honor
     `fullnameOverride`. **The render tells you** — confirm by rendering with the
     release name: `helm template <app> charts/<app> ...`.
  2. If the chart **honors `fullnameOverride`** (e.g. many Bitnami charts) set
     `<chart>.fullnameOverride: <app>` in the wrapper's base `values.yaml` to pin
     it. Adding it can rename resources on the next sync if the chart wasn't
     already producing that name — warn the user.
  Either way, always `helm template <app> charts/<app>` (release name `<app>`,
  not the default `release-name`) and read the actual names before writing the
  manifest.
- **Gate every added manifest on a values flag** — `{{- if .Values.serviceMonitor.enabled }}`
  … `{{- end }}` — default sensible (monitors on), overridable per environment
  through the `$values` overlay in `environments/<env>/values/<app>.yaml`.
- **A resource lives with whatever it is about.** App route/monitor →
  `charts/<app>/`. A shared middleware every app uses → the controller's wrapper
  (`charts/traefik/`). Cluster-wide alert rules → `charts/kube-prometheus-stack/`.
- **CRD-exists is a sync-wave concern.** A ServiceMonitor needs the
  Prometheus-Operator CRD (from the `kube-prometheus-stack` app). That app must
  sit at a lower `argocd.argoproj.io/sync-wave` than apps that ship its CRs. This
  is ordering via `argocd.argoproj.io/sync-wave` on the Applications (the operator
  app at a lower wave), not via where files sit. See
  `reference/hooks-and-waves.md`.
- **A `templates/` change is a chart change** — bump `charts/<app>/Chart.yaml`
  `version`.

## Template context

Available: `.Values` (including `.Values.<chart>.*`), `.Release.Name`,
`.Release.Namespace`, the wrapper's `.Chart`, `.Capabilities`,
`.Values.global.*`.
**Do not use:** the upstream chart's `_helpers.tpl` named templates — never
`{{ include "<upstream>.fullname" . }}`. They resolve (Helm's template namespace
is global) but compute names from the wrong (wrapper) context/values.

## Authoring checklist

1. `helm template <app> charts/<app>` once (release name `<app>`, matching what
   Argo CD uses — not the default `release-name`). Read the real Service names,
   the **named** ports (a ServiceMonitor `endpoints[].port` must be a *name*, not
   a number), and the pod/Service labels the new manifest must select. Some
   charts derive names from the release name and ignore `fullnameOverride`;
   others honor it. **The render tells you** — always
   `helm template <app> charts/<app>` and read the actual names. If the names are
   not `<app>-<component>` and the chart honors `fullnameOverride`, set
   `<chart>.fullnameOverride: <app>` in `charts/<app>/values.yaml` (warn: may
   rename on next sync); if the render already shows `<app>-<component>`, use the
   names as rendered and do not add a no-op `fullnameOverride`.
2. For `servicemonitor` / `podmonitor`: copy the matching
   `reference/starters/<kind>.yaml` into `charts/<app>/templates/` verbatim —
   it is fully values-driven — then write the values stanza (step 3). For any
   other kind: author the template against these conventions.
3. Add the gating values stanza to `charts/<app>/values.yaml` as a **top-level**
   key (not nested under the subchart), e.g.:
   ```yaml
   serviceMonitor:
     enabled: true
     selectorLabels: {app.kubernetes.io/name: <app>, app.kubernetes.io/component: <c>}
     port: metrics
     path: /metrics
     interval: 30s
   ```
4. Never `include` a subchart helper (step "Template context").
5. Verify: `helm dependency build charts/<app>` (or `helm dependency update
   charts/<app>` if there is no `Chart.lock` yet) →
   `helm template <app> charts/<app>` renders your manifest. If a cluster with
   the CRD is reachable:
   `helm template <app> charts/<app> | kubectl apply --dry-run=server -f -`.
6. Bump `charts/<app>/Chart.yaml` `version`.

## References

- `reference/prometheus-operator.md` — how the operator selects ServiceMonitors,
  the named-port rule, defaults, and how to confirm a target is actually scraped.
- `reference/hooks-and-waves.md` — sync-waves vs Argo CD hooks; the traps.

## When an app exposes no metrics

Many apps (Metabase, a bare MySQL) serve no Prometheus endpoint. `helm template`
shows no named `metrics`/`http-metrics` port and no `/metrics`. A ServiceMonitor
then scrapes nothing. Say so and stop — the app needs an exporter sidecar or the
chart's own metrics option first. Wiring that up is the observability workflow
(`argocd-observability`, separate), not this primitive.
