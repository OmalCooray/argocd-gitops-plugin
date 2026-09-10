---
name: argocd-rollout
description: Drive one Argo CD application all the way to Synced + Healthy + actually-functioning — trigger the sync, watch it in bounded steps, and on any stall run the troubleshooting loop (diagnose → fix in git → re-sync) until it converges or a clear blocker is reported. Load whenever a deploy/change needs to end in a working app, not just a merged PR.
---

# Rollout to healthy

A merged PR is not a finished deploy. This is the loop that takes an Argo CD
`Application` from "declared" to "the app works", following the interaction
contract (`${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`) throughout —
announce each step, one status line per check, no open-ended polling.

## Inputs

- `<app>` — the Argo CD Application name (and its destination namespace, read
  from the manifest or `argocd app get`).
- Its git revision must already be on the tracked branch (the deploy PR merged).

## The loop

```
trigger sync ──▶ bounded watch ──▶ Healthy? ──yes──▶ functional check ──▶ done
                      │                 │no
                      │                 ▼
                      │            progressing?  ──yes──▶ (keep watching, bounded)
                      │                 │no (stuck)
                      ▼                 ▼
                 report + stop     troubleshoot → fix in git → merge → back to "trigger sync"
```

### 1. Trigger the sync

If the app has `syncPolicy.automated`, a `hard` refresh is usually enough:

```bash
kubectl -n <argocd-ns> annotate application <app> argocd.argoproj.io/refresh=hard --overwrite
```

To force a sync explicitly without the `argocd` CLI, patch the operation:

```bash
kubectl -n <argocd-ns> patch application <app> --type merge -p \
  '{"operation":{"initiatedBy":{"username":"argocd-rollout"},"sync":{"revision":"HEAD","syncStrategy":{"apply":{"force":true}}}}}'
```

### 2. Bounded watch

Check **at a fixed cadence for a stated ceiling** — e.g. up to 10 checks, ~20 s
apart (~3–4 min). Each check prints one line:

```
[n] <app>  <sync>/<health>  <op message or "">  pods <ready>/<total>
```

Read from:
```bash
kubectl -n <argocd-ns> get application <app> \
  -o jsonpath='{.status.sync.status}/{.status.health.status} | {.status.operationState.phase} | {.status.operationState.message}'
kubectl -n <dest-ns> get pods
```

Stop the watch as soon as one of these is true:
- **Healthy + Synced** → go to step 4.
- **Stuck** (per `argocd-troubleshooting`: `CrashLoopBackOff` / `ImagePullBackOff`
  / `CreateContainerConfigError`; same `operationState.message` for the whole
  window; `operationState.phase: Failed`; `OutOfSync` with no running op) → step 3.
- **Ceiling reached, still Progressing** on image pulls / init containers with no
  errors → report "still rolling out, nothing wrong" and hand back with the exact
  thing it's waiting on. Do not loop forever.

### 3. Troubleshoot → fix → re-sync

- Run the `argocd-troubleshooting` flow: drill to the failing object, match the
  signature, name the **root cause + evidence + fix**.
- The fix is a **git change** (a values key, a manifest annotation, a missing
  Secret created out of band). Make it on a branch, `helm template` to confirm it
  renders, open a PR (checkpoint before push), merge (checkpoint).
- **Deadlocked sync** (op message "waiting for healthy state of X" where X can
  never be healthy until the fix lands): after merging, clear the stuck op, then
  re-trigger:
  ```bash
  kubectl -n <argocd-ns> patch application <app> --type merge -p '{"operation":null}'
  kubectl -n <argocd-ns> patch application <app> --type json -p '[{"op":"remove","path":"/status/operationState"}]'
  ```
- Go back to step 1. Cap the fix cycles (e.g. 4). If it's still not converging,
  stop and report every root cause found so far + what you tried — do not thrash.

### 4. Functional check — Healthy ≠ working

Argo CD health is pod/replica status. Confirm the app actually serves. Pick the
checks that fit the app (see the table); run them via `kubectl exec` or a
short-lived `kubectl port-forward` (foreground, then kill it).

| App type | Functional check |
|---|---|
| HTTP app (Grafana, Metabase, Airflow API, Argo CD) | `GET` its health/readiness path returns 2xx; the login page loads |
| App with an external DB | its own health endpoint reports the DB connection healthy; or `exec` a `SELECT 1`; the app's schema/tables exist in the DB |
| Prometheus | `/-/healthy` 200; `/api/v1/query?query=up` shows targets, most `== 1` |
| Alertmanager | `/-/healthy` 200 |
| Message broker / cache | a client `PING` from another pod |
| Worker/queue system (Airflow) | scheduler + triggerer heartbeats are recent in the health endpoint |
| Operator (prometheus-operator, cert-manager) | it reconciled its CRs — the CRs report Ready, not just the operator pod |
| Extra manifest (ServiceMonitor / PodMonitor / …) | it renders and the CRD accepts it; for a monitor, after sync the target appears in Prometheus `/api/v1/targets` and `up{...}` for the app returns 1 |
| Grafana dashboard | after sync it appears in Grafana's `<app>` folder (`GET /api/search?query=<title>`, `folderTitle == <app>`) and its panels render data — open one, not "No data" |

If a functional check fails while Argo CD says Healthy, that's a real finding —
go back to step 3 with it.

### 5. Report

```
<app>: Synced / Healthy / functioning
rolled out in <n> sync(s); fixes applied: <PR list or "none">
functional checks: <what passed>
UIs / endpoints: <how to reach it>
```

Or, if it didn't converge:

```
<app>: NOT healthy after <n> attempts
blockers found: <root cause(s) + evidence>
tried: <fixes>
next: <what a human needs to decide/provide>
```

## Guardrails

- Never `kubectl edit` / `scale` / `patch` a **workload** to force health — the
  fix is always a git change. The only direct cluster actions allowed are:
  trigger/clear a sync, `annotate ... refresh`, and creating a missing
  out-of-band Secret.
- Never disable a probe or lower a replica count just to make Argo CD go green.
- Bounded everything. A watch has a ceiling; the fix loop has a ceiling.
