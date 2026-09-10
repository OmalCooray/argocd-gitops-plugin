# Prometheus Operator — ServiceMonitor / PodMonitor rules

## How the operator picks up a ServiceMonitor

The `Prometheus` CR has `spec.serviceMonitorSelector` and
`spec.serviceMonitorNamespaceSelector`. A `ServiceMonitor` is scraped only if it
matches **both**.

The `kube-prometheus-stack` chart, with these values (set in this plugin's
prod overlay):

```yaml
prometheus:
  prometheusSpec:
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false
    ruleSelectorNilUsesHelmValues: false
```

makes `serviceMonitorSelector` (and the Pod/rule equivalents) **empty**, so the
`Prometheus` CR matches ServiceMonitors by label = any label, i.e. all of them.

The **cross-namespace** behavior is a separate knob:
`spec.serviceMonitorNamespaceSelector` defaults to `{}`, which means *all
namespaces*. Together the two knobs give "any ServiceMonitor, in any namespace" —
a good default for a platform where apps ship their own monitors. A stricter
install may tighten either one.

A stricter install (selectors not nil) usually requires the label
`release: <kube-prometheus-stack release name>` on the ServiceMonitor. The
starter templates take `serviceMonitor.labels` so you can add it if needed.

## The named-port rule

`ServiceMonitor.spec.endpoints[].port` and
`PodMonitor.spec.podMetricsEndpoints[].port` are the **name** of a port on the
Service / pod, not a number. If the app's Service exposes
`ports: [{name: metrics, port: 9102}]` you write `port: metrics`. `helm template
<app> charts/<app> | grep -A3 'kind: Service'` shows the names. If a port has no name,
there is nothing to reference — the app or chart must name it first.

## Selector

`ServiceMonitor.spec.selector.matchLabels` selects **Services** (not pods). Use
the labels the chart puts on the Service you want scraped — usually
`app.kubernetes.io/name: <app>` plus `app.kubernetes.io/component: <c>` or the
chart's `app`/`release` labels. `PodMonitor.spec.selector` selects **pods**
directly (use pod labels).

The ServiceMonitor's own `spec.namespaceSelector` (the starter's
`serviceMonitor.namespaceSelector` value) — when **absent** — restricts it to
Services in **its own namespace**. So if you set `serviceMonitor.namespace` to
create the ServiceMonitor somewhere other than where the app's Services live, you
**must** also set `serviceMonitor.namespaceSelector` to the app's namespace, or
it scrapes nothing.

## Endpoint defaults the starters apply

| Field | Default | Notes |
|---|---|---|
| `path` | `/metrics` | override for apps that expose elsewhere |
| `scheme` | `http` | `https` needs `tlsConfig` |
| `interval` | `30s` | |
| `scrapeTimeout` | (unset → Prometheus default) | must be < interval |
| `honorLabels` | false | true only for federation / pushgateway-style sources |

`relabelings` run before the scrape (drop targets, rewrite `__address__`);
`metricRelabelings` run after (drop noisy series). Both are pass-through lists in
the starters.

## Confirming it actually works

After the sync (via `/argocd-sync <app>`):

```bash
# target registered and up:
curl -s 'http://<prometheus>/api/v1/targets?state=active' \
  | jq '.data.activeTargets[] | select(.scrapePool | test("<app>")) | {scrapePool, health}'
# a metric from the app is present:
curl -s 'http://<prometheus>/api/v1/query?query=up{job=~".*<app>.*"}' | jq '.data.result'
```

A `ServiceMonitor` that renders and applies but produces no target usually means:
the selector labels don't match any Service; the port name is wrong; or the
namespaceSelector excludes the app's namespace.
