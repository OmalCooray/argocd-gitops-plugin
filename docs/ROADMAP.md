# Roadmap

This project doesn't plan its direction in advance. Argo CD gets used in more ways
than any one person's experience covers, so instead of pre-committing to a feature
list, this roadmap starts empty and grows from what people who actually use the
plugin ask for.

## Now

Nothing is in active development right now. `v0.6.0` just shipped — the focus is
watching how it holds up for real use and picking the first thing to build from
that.

## Want something changed or added?

Open a [GitHub Issue](https://github.com/OmalCooray/argocd-gitops-plugin/issues).
Tell us how you use Argo CD and what's missing or getting in the way — that becomes
a candidate here.

## How a feature actually ships

A real feature (not a docs or infra fix) goes through:
`superpowers:brainstorming` → `superpowers:writing-plans` →
`superpowers:subagent-driven-development` → **live dogfood on a real cluster** →
`superpowers:finishing-a-development-branch`, and gets its own
`docs/superpowers/specs/` + `docs/superpowers/plans/` pair. Infra/docs changes
(CI, changelog, small fixes) can skip formal brainstorming but still land behind
a reviewed PR.

## Explicitly out of scope

- Flux support (the skills are Argo CD-specific by design).
- Own-application chart authoring (`frontend`/`backend` charts you develop) — the registry-chart source type.
- `argocd-exporters` / `/argocd-observe` — a full "provision an exporter → ServiceMonitor → dashboard" orchestrator. The primitives (`/argocd-add-manifest`, `/argocd-add-dashboard`) already exist; the orchestrator is a bigger, separate undertaking.
- Alertmanager routing / receiver management.
- Cost/quota policy, OPA/Kyverno policy scaffolding.
