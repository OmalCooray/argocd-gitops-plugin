#!/usr/bin/env bash
# End-to-end: install Argo CD on the CURRENT kube-context, apply an Application
# that points at a public upstream chart, and confirm it reconciles to
# Synced/Healthy. Intended for a throwaway cluster (docker-desktop, kind).
# Not idempotent-clean.
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

# podinfo via its Helm chart, HPA disabled: the kustomize/ path bundles an
# HorizontalPodAutoscaler, and on a cluster with no metrics-server (kind, plain
# docker-desktop) that HPA never gets metrics, so Argo CD reports it — and the
# whole Application — Degraded indefinitely.
kubectl apply -n "$NS" -f - <<'YAML'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: e2e-podinfo
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://stefanprodan.github.io/podinfo
    chart: podinfo
    targetRevision: 6.7.1
    helm:
      parameters:
        - name: hpa.enabled
          value: "false"
  destination:
    server: https://kubernetes.default.svc
    namespace: e2e-podinfo
  syncPolicy:
    automated: { prune: true, selfHeal: true }
    syncOptions: [CreateNamespace=true]
YAML

dump_diagnostics() {
  echo "== app describe =="
  kubectl describe app e2e-podinfo -n "$NS" || true
  echo "== app resources =="
  kubectl get all -n e2e-podinfo || true
  echo "== pod details =="
  kubectl describe pods -n e2e-podinfo || true
  echo "== events =="
  kubectl get events -n e2e-podinfo --sort-by=.lastTimestamp || true
}

echo ">> waiting for e2e-podinfo to become Healthy/Synced (up to 3m)"
for i in $(seq 1 36); do
  sync=$(kubectl get app e2e-podinfo -n "$NS" -o jsonpath='{.status.sync.status}' 2>/dev/null || true)
  health=$(kubectl get app e2e-podinfo -n "$NS" -o jsonpath='{.status.health.status}' 2>/dev/null || true)
  echo "   [$i] sync=$sync health=$health"
  [ "$sync" = "Synced" ] && [ "$health" = "Healthy" ] && { echo "OK"; exit 0; }
  sleep 5
done
echo "FAIL: e2e-podinfo did not converge"
dump_diagnostics
exit 1
