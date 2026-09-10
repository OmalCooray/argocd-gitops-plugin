---
name: argocd-troubleshooting
description: Diagnose a stuck, degraded, or OutOfSync Argo CD application — read sync/health status, walk the resource tree to the failing object, match the failure signature (image pull, CRD ordering, hook deadlock, OOM, bad values path, unbound PVC, RBAC), and name the fix. Load when an app will not go Healthy/Synced or a deploy appears hung.
---

# Argo CD troubleshooting

Work from evidence, top down. Do **not** wait in a loop for something to become
healthy — inspect it once, decide if it is progressing or stuck, and if stuck,
find why.

## Step 1 — the app's own verdict

```bash
argocd app get <app> -o json            # if the CLI is logged in
# or:
kubectl -n <argocd-ns> get application <app> -o json
```

Read, in this order:
- `status.sync.status` — `Synced` / `OutOfSync`
- `status.health.status` — `Healthy` / `Progressing` / `Degraded` / `Missing`
- `status.operationState.phase` + `.message` — is a sync running, and what is it
  waiting on? `"waiting for healthy state of <kind>/<name>"` names the blocker.
- `status.conditions[]` — `ComparisonError`, `SyncError`, `OrphanedResourceWarning`
- `status.resources[]` — per-object `status` and `health`; find the ones that are
  not `Synced` / not `Healthy`.

**Progressing vs stuck:** compare `status.operationState.startedAt` to now. Under
~2 min with pods pulling images or running init containers = progressing, leave
it. Over ~5 min on the same message, or pods in `CrashLoopBackOff` /
`ImagePullBackOff` / `CreateContainerConfigError` = stuck, keep going.

## Step 2 — drill to the failing object

For the worst resource from `status.resources[]`:

```bash
kubectl -n <dest-ns> get <kind> <name> -o wide
kubectl -n <dest-ns> describe <kind> <name>        # read the Events at the bottom
kubectl -n <dest-ns> get events --sort-by=.lastTimestamp | tail -20
```

For a Deployment/StatefulSet, go to its pods:

```bash
kubectl -n <dest-ns> get pods -l <selector>
kubectl -n <dest-ns> describe pod <pod>            # Events + per-container State/Reason
kubectl -n <dest-ns> logs <pod> --all-containers --tail=50
kubectl -n <dest-ns> logs <pod> -c <initContainer> --tail=50   # init containers matter
kubectl -n <dest-ns> logs <pod> --previous --tail=50           # last crash
```

## Step 3 — match the signature

| What you see | Likely cause | Fix |
|---|---|---|
| Pod `ImagePullBackOff` / `ErrImagePull`; long `Pulling` that never succeeds | image tag does not exist (often a chart `appVersion` placeholder like `x.y.z.x` or `latest` with no such tag) or private registry with no `imagePullSecrets` | pin a real `image.tag` in values; add `imagePullSecrets` |
| Pod `CreateContainerConfigError`; event `secret "X" not found` / `configmap "X" not found` | the manifest references a Secret/ConfigMap that isn't in the namespace (out-of-band secret missing, or a `*SecretName` value pointing at nothing) | create the Secret, or fix the values key to the real name |
| Every workload's init container `CrashLoopBackOff` on "waiting for migrations"/"waiting for db" | the DB-migration Job is a **Helm hook** and Argo CD didn't run it, or the DB is unreachable | `useHelmHooks: false` on the chart's job(s); check the DB Service/pod |
| App `OutOfSync` forever on a `Job`; diff shows a `controller-uid` selector | K8s mutated the started Job's selector; the rendered manifest can't match | annotate the Job `argocd.argoproj.io/hook: Sync` + `hook-delete-policy: BeforeHookCreation` |
| App `OutOfSync` forever on `Secret`s with random-looking names | chart generates random secrets each render (fernet key, jwt, api key, broker url) | set the chart's `*SecretName` values to stable out-of-band Secrets |
| `OutOfSync` on a hand-made resource Argo CD calls "extra" | it carries `app.kubernetes.io/instance: <app>` (e.g. `kubectl apply`-ed over a chart object) | recreate it with no Argo CD labels/annotations |
| Pod `Pending`; event `unbound immediate PersistentVolumeClaims` | no default StorageClass, or the named `storageClass` doesn't exist | set a real `storageClassName`; `kubectl get storageclass` |
| Pod `Pending`; event `Insufficient cpu/memory` | requests exceed node allocatable | lower requests, or scale the cluster |
| Pod `OOMKilled` (in `describe` → Last State) | `limits.memory` too low for the app | raise `resources.limits.memory` |
| Sync fails `the server could not find the requested resource` / `no matches for kind` | a CRD the manifests use isn't installed yet (ordering) | sync the CRD/operator first (sync-wave, or a separate app); `ServerSideApply=true` |
| Sync error `SchemaError` / `spec.X: Invalid value` | bad values produced an invalid manifest | `helm template` locally with the same values and read the offending object |
| App `Missing`, no resources | root app not synced, or `path`/`targetRevision` wrong | check the Application `spec.source(s)`; `argocd-audit` |
| Hook Job `PostSync` never runs; components never healthy | deadlock — components wait on a hook that only runs after they're healthy | make the job a `Sync` (not `PostSync`) hook, or a plain resource |

## Step 4 — confirm the fix in git, not the cluster

The fix is a values or manifest change committed to the GitOps repo, then a sync.
Only touch the cluster directly to (a) create a missing out-of-band Secret or
(b) clear a stuck sync operation:

```bash
kubectl -n <argocd-ns> patch application <app> --type merge -p '{"operation":null}'
kubectl -n <argocd-ns> patch application <app> --type json -p '[{"op":"remove","path":"/status/operationState"}]'
kubectl -n <argocd-ns> annotate application <app> argocd.argoproj.io/refresh=hard --overwrite
```

Never `kubectl edit` a workload to work around a values bug — the next sync
reverts it and the drift hides the real problem.

## Offline mode

No cluster access? Ask the user to paste:
- `argocd app get <app> -o yaml` (or `kubectl get application <app> -n argocd -o yaml`)
- `kubectl get pods -n <dest-ns> -o wide`
- `kubectl describe pod <failing-pod> -n <dest-ns>`
- `kubectl logs <failing-pod> -n <dest-ns> --all-containers --tail=100`

The signature table above works the same on pasted output.
