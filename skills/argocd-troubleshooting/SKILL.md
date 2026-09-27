---
name: argocd-troubleshooting
description: Diagnose a stuck, degraded, or OutOfSync Argo CD application — read sync/health status, walk the resource tree to the failing object, match the failure signature (image pull, CRD ordering, hook deadlock, OOM, bad values path, unbound PVC, RBAC), and name the fix. Load when an app will not go Healthy/Synced or a deploy appears hung.
---

# Argo CD troubleshooting

> `$CTX` and `$ARGOCD_NS` come from `${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`; the calling command must have resolved them. If they are unset, run that procedure first.

Work from evidence, top down. Do **not** wait in a loop for something to become
healthy — inspect it once, decide if it is progressing or stuck, and if stuck,
find why.

## Step 1 — the app's own verdict

```bash
argocd app get <app> -o json            # if the CLI is logged in
# or:
kubectl --context "$CTX" -n "$ARGOCD_NS" get application <app> -o json
```

Read, in this order:
- `status.sync.status` — `Synced` / `OutOfSync`
- `status.health.status` — `Healthy` / `Progressing` / `Degraded` / `Missing`
- `status.operationState.phase` + `.message` — is a sync running, and what is it
  waiting on? `"waiting for healthy state of <kind>/<name>"` names the blocker.
- `status.conditions[]` — `ComparisonError`, `SyncError`, `OrphanedResourceWarning`
- `status.resources[]` — per-object `status` and `health`; find the ones that are
  not `Synced` / not `Healthy`. On recent Argo CD the entries often have `status` but no
  `health`: when `status.resources[].health` is empty, fall back to pod/Event state
  (`kubectl --context "$CTX" -n <dest-ns> get pods`, then `describe`).

**Progressing vs stuck:** compare `status.operationState.startedAt` to now. Under
~2 min with pods pulling images or running init containers = progressing, leave
it. Over ~5 min on the same message, or pods in `CrashLoopBackOff` /
`ImagePullBackOff` / `CreateContainerConfigError` = stuck, keep going.

## Step 2 — drill to the failing object

For the worst resource from `status.resources[]`:

```bash
kubectl --context "$CTX" -n <dest-ns> get <kind> <name> -o wide
kubectl --context "$CTX" -n <dest-ns> describe <kind> <name>        # read the Events at the bottom
kubectl --context "$CTX" -n <dest-ns> get events --sort-by=.lastTimestamp | tail -20
```

For a Deployment/StatefulSet, go to its pods:

```bash
kubectl --context "$CTX" -n <dest-ns> get pods -l <selector>
kubectl --context "$CTX" -n <dest-ns> describe pod <pod>            # Events + per-container State/Reason
kubectl --context "$CTX" -n <dest-ns> logs <pod> --all-containers --tail=5
kubectl --context "$CTX" -n <dest-ns> logs <pod> -c <initContainer> --tail=5   # init containers matter (use --tail=50 only to read more)
kubectl --context "$CTX" -n <dest-ns> logs <pod> --previous --tail=5            # last crash
```

## Step 3 — match the signature

| What you see | Likely cause | Fix |
|---|---|---|
| Pod `ImagePullBackOff` / `ErrImagePull`; long `Pulling` that never succeeds | image tag does not exist (often a chart `appVersion` placeholder like `x.y.z.x` or `latest` with no such tag) or private registry with no `imagePullSecrets` | pin a real `<chart>.image.tag` in values, where `<chart>` is the wrapper `charts/<app>/Chart.yaml` `dependencies[0].name` (it may differ from the app name); an own-app chart has no `dependencies`, so its keys are top-level; a bare `image.tag` in a wrapper does nothing; add `imagePullSecrets` |
| Pod `CreateContainerConfigError`; event `secret "X" not found` / `configmap "X" not found` | the manifest references a Secret/ConfigMap that isn't in the namespace (out-of-band secret missing, or a `*SecretName` value pointing at nothing) | create the Secret, or fix the values key to the real name |
| Every workload's init container `CrashLoopBackOff` on "waiting for migrations"/"waiting for db" | the DB-migration Job is a **Helm hook** and Argo CD didn't run it, or the DB is unreachable | `useHelmHooks: false` on the chart's job(s); check the DB Service/pod |
| App `OutOfSync` forever on a `Job`; diff shows a `controller-uid` selector | K8s mutated the started Job's selector; the rendered manifest can't match | annotate the Job `argocd.argoproj.io/hook: Sync` + `hook-delete-policy: BeforeHookCreation` |
| App `OutOfSync` forever on `Secret`s with random-looking names | chart generates random secrets each render (fernet key, jwt, api key, broker url) | set the chart's `*SecretName` values to stable out-of-band Secrets |
| `OutOfSync` on a hand-made resource Argo CD calls "extra" | it carries `app.kubernetes.io/instance: <app>` (e.g. `kubectl apply`-ed over a chart object) | recreate it with no Argo CD labels/annotations |
| Pod `Pending`; event `unbound immediate PersistentVolumeClaims` | no default StorageClass, or the named `storageClass` doesn't exist | set a real `storageClassName`; `kubectl --context "$CTX" get storageclass` |
| Pod `Pending`; event `Insufficient cpu/memory` | requests exceed node allocatable | lower requests, or scale the cluster |
| Pod `OOMKilled` (in `describe` → Last State) | `limits.memory` too low for the app | raise `resources.limits.memory` |
| Sync fails `the server could not find the requested resource` / `no matches for kind` | a CRD the manifests use isn't installed yet (ordering) | sync the CRD/operator first (sync-wave, or a separate app); `ServerSideApply=true` |
| Sync error `SchemaError` / `spec.X: Invalid value` | bad values produced an invalid manifest | `helm template` locally with the same values and read the offending object |
| App `Missing`, no resources | root app not synced, or `path`/`targetRevision` wrong | check the Application `spec.source(s)`; `argocd-audit` |
| Hook Job `PostSync` never runs; components never healthy | deadlock — components wait on a hook that only runs after they're healthy | make the job a `Sync` (not `PostSync`) hook, or a plain resource |
| Sync fails `Deployment.apps "X" is invalid: spec.selector: … field is immutable` (also under `ServerSideApply=true`, this plugin's default — SSA does not lift the immutability) | a values/chart change altered the Deployment's selector labels; K8s forbids it | first choice: revert the label/selector change in git. If the change is intended, put the per-resource annotation `argocd.argoproj.io/sync-options: Replace=true` on that Deployment only (not app-wide `syncOptions`); **this deletes and recreates the Deployment: expect downtime, and check for PVCs first**. REMOVE the annotation again in a follow-up commit once the sync succeeds. Never delete the workload by hand |
| Pod `Running` but `0/1` Ready, readiness 500, logs show `x509: cannot validate certificate for <ip> because it doesn't contain any IP SANs` | the app (e.g. metrics-server) cannot verify the kubelet's self-signed serving certs. Local cluster = kube-context named `kind-*`, `docker-desktop`, `minikube`, `k3d-*` or `rancher-desktop` | **local clusters only**: in `environments/<env>/values/<app>.yaml` set `<dependency-name>.args: [--kubelet-insecure-tls]` (for the metrics-server wrapper chart the dependency name is `metrics-server`); env overlay, never the shared catalog values; see the metrics-server section of `${CLAUDE_PLUGIN_ROOT}/skills/values-review/reference/chart-notes.md` when present. `--kubelet-insecure-tls` is NEVER proposed for any other cluster: there the correct fix is kubelet serving certificates (`serverTLSBootstrap` + approved CSRs), a cluster-level decision — report it and stop |
| Pod `CrashLoopBackOff`, `describe` → `Exit Code` ≠ 0 (2 = bad CLI usage), no init container involved | the app rejects its own flags/config — usually a bad `extraArgs`/`command`/env value | read `kubectl --context "$CTX" -n <dest-ns> logs <pod> --previous --tail=5` (the error is on the last lines); fix the offending key in values |

**Running but not Ready** does not match the `CrashLoopBackOff`/`ImagePullBackOff` stuck
signatures — look at readiness events and `logs --tail=5`. Treat a `Running` pod as stuck
when it is still not Ready after the readiness probe's `initialDelaySeconds +
failureThreshold × periodSeconds` (read from the pod spec) or 5 minutes, whichever is
shorter; but if the readiness events show a hard error (HTTP 5xx, `x509`, connection
refused) and the same error is in the logs, diagnose as soon as the error is evident; do
not wait. (An unavailable APIService such as `v1beta1.metrics.k8s.io` reporting
`Available=False (MissingEndpoints)` is the matching symptom for metrics-server).

An app with a bad rollout stays `Progressing` — not `Degraded` — until the Deployment's
600 s `progressDeadlineSeconds` expires; pod signatures, not the Argo health colour, are the
stuck test.

Use `--tail=5 --previous` for logs (the real error is on the last lines); if the tail is a
usage/`--help` dump, filter instead of dumping 50 lines:
`kubectl --context "$CTX" -n <dest-ns> logs <pod> --previous | grep -m3 -iE 'error|invalid|fatal'`.

## Step 4 — confirm the fix in git, not the cluster

The fix is a values or manifest change committed to the GitOps repo, then a sync.
Never `kubectl edit` a workload to work around a values bug — the next sync
reverts it and the drift hides the real problem.

### Triggering a sync (no `argocd` CLI needed)

```bash
# usually enough for an app with syncPolicy.automated:
kubectl --context "$CTX" -n "$ARGOCD_NS" annotate application <app> argocd.argoproj.io/refresh=hard --overwrite
```

If a refresh is not enough, use the escalation ladder in `argocd-rollout` step 1 (refresh →
plain sync → force only after an immutable-field/selector failure, behind a second
checkpoint). Do not force-sync directly from here.

### Clearing a deadlocked sync

**Signature:** `status.operationState.phase: Running` for a long time,
`message: "waiting for healthy state of <kind>/<name>"`, and that object can't
become healthy until a fix that's already merged is applied — but the running
operation won't re-render to apply it. The sync is waiting on the thing the sync
needs to fix.

**Recipe** (after the fix is merged to the tracked branch):

```bash
kubectl --context "$CTX" -n "$ARGOCD_NS" patch application <app> --type merge -p '{"operation":null}'
kubectl --context "$CTX" -n "$ARGOCD_NS" patch application <app> --type json -p '[{"op":"remove","path":"/status/operationState"}]'
kubectl --context "$CTX" -n "$ARGOCD_NS" annotate application <app> argocd.argoproj.io/refresh=hard --overwrite
# if automated sync doesn't re-trigger within ~30s, use the escalation ladder in `argocd-rollout` step 1
```

The only direct cluster actions troubleshooting ever takes: trigger/clear a sync,
`annotate refresh`, and creating a missing out-of-band Secret.

## Offline mode

No cluster access? Ask the user to paste:
- `argocd app get <app> -o yaml` (or `kubectl --context "$CTX" get application <app> -n "$ARGOCD_NS" -o yaml`)
- `kubectl --context "$CTX" get pods -n <dest-ns> -o wide`
- `kubectl --context "$CTX" describe pod <failing-pod> -n <dest-ns>`
- `kubectl --context "$CTX" logs <failing-pod> -n <dest-ns> --all-containers --tail=100`

The signature table above works the same on pasted output.
