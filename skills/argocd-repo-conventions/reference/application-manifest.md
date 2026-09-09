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
