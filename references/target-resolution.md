# Resolve the target cluster (run this first in every cluster-touching command)

`kubectl` and `helm` act on whatever kube-context is *current*. On a machine that
also has a production cluster that is a silent foot-gun, so resolve and confirm
the target before the first cluster command.

1. Read `.claude/CLAUDE.md` in the GitOps repo: `Argo CD namespace` → `ARGOCD_NS`,
   `GitOps repo URL` → `REPO_URL`. (Never assume `argocd`.)
2. Choose the kube-context `CTX`: the value of `--context <name>` if the user gave
   one, otherwise the output of `kubectl config current-context` (read-only).
3. Print exactly one line: `Target: context=<CTX>  argocd-ns=<ARGOCD_NS>  repo=<REPO_URL>`.
4. If the user did **not** name a context, checkpoint (one line, wait for yes):
   `> About to act on kube-context "<CTX>" (your current context). Proceed?`
5. Probe reachability once: `kubectl --context "<CTX>" cluster-info --request-timeout=5s`.
   On failure print ONE plain line — `Cluster "<CTX>" is not reachable: start it or pass --context <name>` — and stop
   (or switch to the command's offline mode if it has one). Do not paste the raw
   multi-line connection error.
6. Every later cluster command carries `--context "<CTX>"`; `helm install|upgrade|list`
   carry `--kube-context "<CTX>"`. Local-only helm (`template|lint|show|dependency|search|repo`)
   needs neither. Never `kubectl config use-context`.
