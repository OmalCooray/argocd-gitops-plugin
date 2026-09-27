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
    assert steps.index("Validate the environment") < steps.index("Build the **declared set**")
    assert "Read-only" in a
    assert "Never run `argocd app sync` for an app that is missing" in a
    assert "${CLAUDE_PLUGIN_ROOT}/commands/argocd-sync.md" in steps
    assert "unknown (could not reach the repo)" in steps
    assert "root app never applied" in steps and "/argocd-bootstrap" in steps
    assert "kubectl apply" in steps and "unmanaged by GitOps" in steps


def test_audit_root_exemption_managed_by_and_cross_env():
    a = read("commands/argocd-audit.md")
    assert "exempt from the Managed-by test and from the unmanaged count" in a
    assert "root (bootstrap)" in a
    assert "root app: LIVE|MISSING" in a
    for needle in ("not this env's root", "manually applied / unknown", "belongs to <env>",
                   "app.kubernetes.io/instance", "chart version differs",
                   "Validate `$1` (Step 0) first"):
        assert needle in a, needle
    head = a.split("---", 2)[1]
    assert "root app" in head and "root.yaml" in head


def test_audit_summary_line_template_is_complete():
    a = read("commands/argocd-audit.md")
    line = next(l for l in a.splitlines() if "declared (+root)" in l)
    for word in ("declared", "+root", "live", "missing", "orphaned", "drifted", "unhealthy",
                 "unmanaged", "unknown", "<u>"):
        assert word in line, word
    i = a.index("No drift")
    window = a[max(0, i - 200):i + 200]
    assert "unknown" in window and "0" in window


REFUSED = ["system:anonymous", "system:authenticated", "system:masters", "system:unauthenticated"]


def _norm(s):
    return " ".join(s.split())


def _refusal_subjects(text):
    line = next(l.strip() for l in text.splitlines() if l.strip().startswith("- refuse outright"))
    assert "no override" in line and "even if the user insists" in line
    return sorted(set(re.findall(r"system:(?:authenticated|unauthenticated|anonymous|masters)", line)))


def _guardrail_block(text):
    start = text.index("A kind is *privileged* if")
    end = text.index("before committing.", start) + len("before committing.")
    return _norm(text[start:end])


def test_add_manifest_has_guardrail_and_crd_path():
    m = read("commands/argocd-add-manifest.md")
    s = read("skills/argocd-extra-manifests/SKILL.md")
    for needle in ("system:authenticated", "refuse", "enabled: false",
                   "servicemonitors.monitoring.coreos.com", "prometheus-operator-crds", "sync-wave"):
        assert needle in m, needle
    assert "## Privileged kinds" in s

    # guardrail precedes the authoring instruction
    assert m.index("privileged-kind guardrail") < m.index("author `charts/<app>/templates/<slug>.yaml`")

    # refusal is absolute, names all four subjects, identical in both files
    assert _refusal_subjects(m) == REFUSED
    assert _refusal_subjects(s) == REFUSED
    assert "> This grants <X> to <Y>. Proceed?" in m

    # effective-grant rule and no drift between command and skill
    for text in (m, s):
        assert "effective grant" in text and "resolves to" in text
        assert "system:serviceaccounts:<ns>" in text
    assert _guardrail_block(m) == _guardrail_block(s)
    assert "benign namespaced Role" in m and "`escalate`" in m and "`pods/exec`" in m

    # CRD check step
    step6 = m.split("\n6. CRD check", 1)[1].split("\n7. Verify", 1)[0]
    for needle in ("servicemonitors.monitoring.coreos.com", "podmonitors.monitoring.coreos.com",
                   "prometheus-operator-crds", "sync-wave", "https://prometheus-community.github.io/helm-charts",
                   "any provider", "kubectl --context \"$CTX\" get crd", "--include-crds",
                   "helm dependency build \"$T/", "crds.enabled: false",
                   "argocd.argoproj.io/sync-wave", "missing annotation means",
                   "strictly lower", "serviceMonitor.enabled: true", "podMonitor.enabled"):
        assert needle in step6, needle
    assert "report it and stop" not in step6
    assert "helm dependency build charts/" not in step6

    # gate default follows the CRD check
    step5 = m.split("\n5. Add the gating values stanza", 1)[1].split("\n6. CRD check", 1)[0]
    assert "finalized in step 6" in step5


def test_init_repo_no_author_defaults_and_asks_visibility():
    t = read("commands/argocd-init-repo.md")
    assert "OmalCooray" not in t
    assert "gh api user" in t and "init.defaultBranch" in t and "Visibility" in t
    assert "render_template.py" in t
    assert "--private" not in t.replace("--$VISIBILITY", "")


def test_install_script_requires_an_explicit_context_and_prints_access_hints():
    s = read("templates/install.sh.tmpl")
    assert '${1:?' in s and "port-forward" in s and "initial-admin-secret" in s
    heredoc = s.split("cat <<EOF", 1)[1]
    kube = [ln for ln in heredoc.splitlines() if "kubectl" in ln]
    assert kube and all("--context" in ln for ln in kube), kube
    assert "install.sh <kube-context>" in read("templates/gitops-README.md.tmpl")


def test_commands_render_via_the_script_not_prose():
    for rel in ("commands/argocd-add-chart.md", "commands/argocd-deploy.md", "agents/argocd-onboarder.md"):
        assert "render_template.py" in read(rel), rel


def test_no_unquoted_plugin_root_python_calls():
    import subprocess
    files = subprocess.run(["git", "ls-files", "commands", "agents", "skills", "references"],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    for rel in files:
        if rel.endswith(".md"):
            assert "python ${CLAUDE_PLUGIN_ROOT}" not in read(rel), rel
    assert "python3" in read("references/interaction-style.md")


def test_init_repo_has_creation_checkpoint_and_sets_remote_url():
    t = read("commands/argocd-init-repo.md")
    assert "About to create" in t and "git remote set-url origin" in t


def _render_calls():
    calls = []
    files = sorted((ROOT / "commands").glob("*.md")) + sorted((ROOT / "agents").glob("*.md"))
    for path in files:
        text = path.read_text(encoding="utf-8")
        for block in re.findall(r"```[a-z]*\n(.*?)```", text, flags=re.S):
            joined = re.sub(r"\\\n\s*", " ", block)
            for line in joined.splitlines():
                if line.lstrip().startswith("R=") or not ("render_template.py" in line or line.lstrip().startswith("$R ")):
                    continue
                tmpl = re.search(r"([A-Za-z0-9._-]+\.tmpl)", line)
                assert tmpl, (path.name, line)
                rest = line.split(tmpl.group(1), 1)[1]
                keys = set(re.findall(r"(?<![A-Za-z0-9_])([A-Z][A-Z0-9_]*)=", rest))
                calls.append((path.name, tmpl.group(1), keys))
    return calls


def test_render_calls_match_template_placeholders():
    calls = _render_calls()
    assert len(calls) >= 8, calls
    rendered = set()
    for cmd, tmpl, keys in calls:
        path = ROOT / "templates" / tmpl
        assert path.exists(), (cmd, tmpl)
        expected = set(re.findall(r"\{\{\s*([A-Z0-9_]+)\s*\}\}", path.read_text(encoding="utf-8")))
        assert keys == expected, (cmd, tmpl, sorted(keys ^ expected))
        rendered.add(tmpl)
    never = sorted(p.name for p in (ROOT / "templates").glob("*.tmpl") if p.name not in rendered)
    assert never == [], never


def test_bootstrap_handles_private_repos_with_a_deploy_key():
    b = read("commands/argocd-bootstrap.md")
    for needle in ("gh repo view", "ssh-keygen", "deploy-key add", "argocd.argoproj.io/secret-type=repository", "sshPrivateKey"):
        assert needle in b, needle
    assert "head -5" not in b
    assert "read-only deploy key" in b.lower()
    assert "--allow-write" not in b


def _bootstrap_step8(b):
    return b[b.index("8. **Private-repo access**"):b.index("9. FINAL-CHECK")]


def test_bootstrap_private_repo_step_runs_after_install_and_before_final_check():
    b = read("commands/argocd-bootstrap.md")
    # Anchor on the real commands; step 9 carries the FINAL-CHECK marker so the
    # last "Synced" (the final check) is what we order against.
    order = [b.find('install.sh "$CTX"'), b.find("gh repo view"), b.find("deploy-key add"),
             b.find("create secret"), b.find("refresh=hard"), b.rfind("Synced")]
    assert -1 not in order and order == sorted(order), order
    assert b.index("9. FINAL-CHECK") < b.rfind("Synced")


def test_bootstrap_step8_never_reads_secret_data_or_traces():
    s = _bootstrap_step8(read("commands/argocd-bootstrap.md"))
    for bad in ("-o yaml", "describe secret", "set -x"):
        assert bad not in s, bad
    assert not re.search(r"get secret[^\n]*-o (?!jsonpath='\{\.data\.url\}')", s)


def test_bootstrap_private_repo_wording_and_rewrite():
    b = read("commands/argocd-bootstrap.md")
    for needle in ('kubectl --context "$CTX" apply -n "$ARGOCD_NS" -f environments/<env>/root.yaml',
                   "ref: values", "both sources", "READ-ONLY deploy key", "create Secret",
                   "SSH agent requested but SSH_AUTH_SOCK not-specified",
                   "authentication required: Repository not found", ".status.conditions[*].message",
                   "json.load(sys.stdin)"):
        assert needle in b, needle
    assert "head -5" not in b
    assert "repository not accessible" not in b
    assert "deploy key or credential Secret" in read("references/interaction-style.md")


def test_bootstrap_never_prints_the_private_key():
    b = read("commands/argocd-bootstrap.md")
    for bad in ('cat "$KEY"', 'echo "$KEY"', "cat $KEY", "echo $KEY"):
        assert bad not in b, bad


def test_bootstrap_marks_install_script_executable():
    assert "--chmod=+x" in read("commands/argocd-bootstrap.md")


def test_bootstrap_documents_env_flag_and_existing_secret_url_check():
    b = read("commands/argocd-bootstrap.md")
    head = b.split("---", 2)[1]
    assert "[--env <environment>]" in head
    assert "environment is chosen with `--env <name>`" in b
    assert "{.data.url}" in b and "base64 -d" in b and "NEVER read `.data.sshPrivateKey`" in b
    assert "read_only" in b and "readOnly" not in b
    assert "ONE `bootstrap/install.sh` per repo" in b


def test_target_resolution_probe_prints_nothing_on_success():
    t = read("references/target-resolution.md")
    assert "On success print nothing" in t and "exactly ONE plain line" in t


def test_doctor_and_troubleshooting_cover_live_findings():
    d = read("commands/argocd-doctor.md")
    s = read("skills/argocd-troubleshooting/SKILL.md")
    for needle in ("healthy — nothing to fix", "not found", "inspected:", "<chart>.image.tag", "Progressing", "--tail=5"):
        assert needle in d + s, needle
    for needle in ("field is immutable", "x509", "Exit Code", "Running but not Ready"):
        assert needle in s, needle
    assert 'image.tag "v0.61.1.x"' not in d


def test_doctor_healthy_branch_precedes_drilldown_and_fix_flow_is_explicit():
    d = read("commands/argocd-doctor.md")
    assert d.index("healthy — nothing to fix") < d.index("walk `status.resources[]`")
    assert d.index("**Unknown app.**") < d.index("walk `status.resources[]`")
    assert "[--fix]" in d.split("---")[1]
    for needle in ("About to push fix/", "git switch -c fix/", "helm template <app> charts/<app> -n",
                   "no-remote-fallback.md", "helm dependency build", "declared but not live"):
        assert needle in d, needle
    assert "the way `/argocd-deploy` does" not in d


def test_troubleshooting_has_new_signature_rows_and_defers_force_to_rollout():
    s = read("skills/argocd-troubleshooting/SKILL.md")
    for needle in ("field is immutable", "x509: cannot validate certificate", "Exit Code",
                   "progressDeadlineSeconds", "argocd-rollout", "status.resources[].health"):
        assert needle in s, needle
    assert '"force":true' not in s
    assert '{"operation":null}' in s
