"""Regression tests: each fixed live-test defect stays fixed."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Commands/agents that contact a cluster or Argo CD and so must resolve the target first.
CLUSTER_COMPONENTS = [
    "commands/argocd-bootstrap.md",
    "commands/argocd-audit.md",
    "commands/argocd-doctor.md",
    "commands/argocd-sync.md",
    "commands/argocd-deploy.md",
    "commands/argocd-add-chart.md",
    "commands/argocd-add-manifest.md",
    "commands/argocd-add-dashboard.md",
    "commands/argocd-review-values.md",
    "agents/argocd-onboarder.md",
]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def fenced_lines(text):
    """Yield lines that are inside ``` fences."""
    inside = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            inside = not inside
            continue
        if inside:
            yield line


ALLOWED_KUBECTL = re.compile(r"kubectl\s+(config\s|version\s+--client)")


def scanned_files():
    """Every command, agent and skill markdown file."""
    files = []
    for pattern in ("commands/*.md", "agents/*.md", "skills/**/*.md"):
        files += [str(p.relative_to(ROOT)).replace("\\", "/") for p in ROOT.glob(pattern)]
    return sorted(files)


def prose_without_fences(text):
    out, inside = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            inside = not inside
            continue
        if not inside:
            out.append(line)
    return "\n".join(out)


def code_part(line):
    """The line without a trailing shell comment."""
    return re.sub(r"\s#.*$", "", line)


def bare_kubectl_segments(line):
    """Cluster-contacting kubectl segments in `line` that lack --context."""
    bad = []
    line = code_part(line)
    for seg in re.split(r"\||&&|;", line):
        if re.search(r"\bkubectl\s", seg) and "--context" not in seg and not ALLOWED_KUBECTL.search(seg):
            bad.append(seg.strip())
    return bad


def test_target_resolution_reference_exists_and_is_complete():
    t = read("references/target-resolution.md")
    for needle in ("Target: context=", "--context", "cluster-info", "Proceed?", ".claude/CLAUDE.md"):
        assert needle in t, needle


def test_every_cluster_component_resolves_the_target_first():
    for rel in CLUSTER_COMPONENTS:
        t = read(rel)
        assert "target-resolution.md" in t, f"{rel} must reference target-resolution.md"
        assert re.search(r"^0\. \*\*Resolve the target", t, re.M), f"{rel}: missing step 0"
        if rel.startswith("commands/"):
            hint = re.search(r"^argument-hint:.*$", t, re.M)
            assert hint and "--context" in hint.group(0), f"{rel}: argument-hint lacks --context"


def test_no_bare_kubectl_in_fenced_examples():
    for rel in scanned_files():
        for line in fenced_lines(read(rel)):
            for seg in bare_kubectl_segments(line):
                raise AssertionError(f"{rel}: kubectl without --context: {seg}")


def test_no_bare_kubectl_in_inline_code():
    for rel in scanned_files():
        for span in re.findall(r"`([^`]+)`", prose_without_fences(read(rel))):
            # A span naming only a verb ("kubectl edit") is prose, not a runnable command.
            if re.search(r"\bkubectl\s+\S+\s+\S", span) and bare_kubectl_segments(" ".join(span.split())):
                raise AssertionError(f"{rel}: inline kubectl without --context: {span.strip()}")


def test_helm_cluster_commands_use_kube_context():
    for rel in scanned_files():
        for line in fenced_lines(read(rel)):
            if re.search(r"\bhelm\s+(install|upgrade|list|uninstall)\b", code_part(line)):
                assert "--kube-context" in line, f"{rel}: helm without --kube-context: {line.strip()}"


def test_no_argocd_ns_placeholder_left():
    import subprocess
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    for rel in files:
        if rel.startswith("docs/superpowers/") or rel == "tests/test_contracts.py":
            continue
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        assert "<argocd-ns>" not in text, f"{rel} still has <argocd-ns>"


def test_bootstrap_runs_install_with_the_resolved_context():
    assert 'install.sh "$CTX"' in read("commands/argocd-bootstrap.md")


def test_sync_has_noop_exit_checkpoint_and_no_head_force():
    sync = read("commands/argocd-sync.md")
    roll = read("skills/argocd-rollout/SKILL.md")
    assert "nothing to do" in sync.lower()
    assert "About to trigger a sync" in sync
    assert '"revision":"HEAD"' not in roll and '"revision": "HEAD"' not in roll
    assert "refresh=hard" in roll                     # refresh is the default trigger


def test_sync_operation_patches_never_pin_a_revision():
    import json
    for rel in ("skills/argocd-rollout/SKILL.md", "skills/argocd-troubleshooting/SKILL.md"):
        patches = re.findall(r"'(\{\"operation\".*?\})'(?:\s|$)", read(rel))
        assert patches, rel
        for raw in patches:
            op = json.loads(raw)["operation"]
            if op is None:
                continue
            assert "revision" not in op["sync"] and "revisions" not in op["sync"], (rel, raw)


def test_sync_noop_exit_precedes_checkpoint_and_ceilings_are_stated():
    sync = read("commands/argocd-sync.md")
    roll = read("skills/argocd-rollout/SKILL.md")
    assert sync.find("nothing to do") < sync.find("About to trigger a sync")
    assert "12 minutes" in sync
    assert "hard cap" in roll


def test_rollout_has_plain_sync_then_force_ladder():
    roll = read("skills/argocd-rollout/SKILL.md")
    assert '"apply":{}' in roll                        # plain sync first
    assert "second checkpoint" in roll.lower()
    assert "DELETE and RECREATE" in roll


def test_audit_covers_root_env_validation_and_multisource():
    a = read("commands/argocd-audit.md")
    for needle in ("environments/<env>/root.yaml", "not found; available environments",
                   "status.sync.revisions", "spec.sources", "missing", "orphaned",
                   "Managed by", "top-level array"):
        assert needle in a, needle


def test_audit_steps_are_ordered_and_safe():
    a = read("commands/argocd-audit.md")
    steps = a.split("## Steps", 1)[1]
    assert steps.index("Validate the environment") < steps.index("declared set")
    assert "Read-only" in a
    assert "Never run `argocd app sync` for an app that is missing" in a
    assert "commands/argocd-sync.md" in steps  # reuses the per-source comparison rules
    assert "unknown (could not reach the repo)" in steps
    assert "root app never applied" in steps and "/argocd-bootstrap" in steps
    assert "kubectl apply (no root app)" in steps and "unmanaged by GitOps" in steps
    # every 'argocd app sync' mention is a prohibition, never a recommendation
    for line in a.splitlines():
        if "argocd app sync" in line:
            assert re.search(r"[Nn]ever", line), line


def test_audit_summary_line_template_is_complete():
    a = read("commands/argocd-audit.md")
    line = next(l for l in a.splitlines() if "declared (+root)" in l)
    for word in ("declared", "live", "missing", "orphaned", "drifted", "unhealthy", "unmanaged"):
        assert word in line, word
