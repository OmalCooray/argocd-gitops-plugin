"""scripts/helm_deps.sh and scripts/render_chart.sh: dependency handling without the user's repo list."""
import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEPS = (ROOT / "scripts" / "helm_deps.sh").as_posix()
RENDER = (ROOT / "scripts" / "render_chart.sh").as_posix()
BASH = shutil.which("bash")
HELM = shutil.which("helm")

pytestmark = pytest.mark.skipif(BASH is None, reason="bash not available")


def sh(script, *args, env=None):
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.run([BASH, script, *map(str, args)], capture_output=True, text=True, env=e)
    return p.returncode, p.stdout, p.stderr


def chart(tmp_path, deps_yaml="", name="mychart"):
    d = tmp_path / name
    (d / "templates").mkdir(parents=True)
    (d / "Chart.yaml").write_text(
        f"apiVersion: v2\nname: {name}\nversion: 0.1.0\n{deps_yaml}", encoding="utf-8", newline="\n")
    (d / "values.yaml").write_text("replicaCount: 3\n", encoding="utf-8", newline="\n")
    (d / "templates" / "deploy.yaml").write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {{ .Release.Name }}\n"
        "  namespace: {{ .Release.Namespace }}\nspec:\n  replicas: {{ .Values.replicaCount }}\n",
        encoding="utf-8", newline="\n")
    return d


def test_print_repos_dedups_and_skips_oci_and_file(tmp_path):
    d = chart(tmp_path, """dependencies:
  - {name: a, version: 1.0.0, repository: "https://charts.example.com"}
  - {name: b, version: 1.0.0, repository: "https://charts.example.com"}
  - {name: c, version: 1.0.0, repository: "oci://ghcr.io/x"}
  - {name: d, version: 1.0.0, repository: "file://../d"}
  - {name: e, version: 1.0.0, repository: "http://other.example.org/charts"}
""")
    rc, out, _ = sh(DEPS, d, "--print-repos")
    assert rc == 0
    assert out.splitlines() == ["http://other.example.org/charts", "https://charts.example.com"]


def test_print_repos_alias_is_an_error(tmp_path):
    d = chart(tmp_path, 'dependencies:\n  - {name: a, version: 1.0.0, repository: "@bitnami"}\n')
    rc, out, err = sh(DEPS, d, "--print-repos")
    assert rc == 1 and out == ""
    assert err.startswith("error:") and "alias" in err and "URL" in err and err.count("\n") == 1


def test_print_repos_no_dependencies_is_empty(tmp_path):
    rc, out, _ = sh(DEPS, chart(tmp_path), "--print-repos")
    assert (rc, out) == (0, "")


def test_missing_chart_yaml_is_an_error(tmp_path):
    rc, _, err = sh(DEPS, tmp_path, "--print-repos")
    assert rc == 1 and err.startswith("error:") and "Chart.yaml" in err


@pytest.mark.skipif(HELM is None, reason="helm not available")
def test_render_own_app_chart_applies_release_ns_and_leaves_source_untouched(tmp_path):
    d = chart(tmp_path)
    vals = tmp_path / "v.yaml"
    vals.write_text("replicaCount: 5\n", encoding="utf-8", newline="\n")
    before = sorted(str(p.relative_to(d)) for p in d.rglob("*"))
    rc, out, err = sh(RENDER, d, "myrel", "myns", "--values", vals)
    assert rc == 0, err
    assert "name: myrel" in out and "namespace: myns" in out and "replicas: 5" in out
    assert sorted(str(p.relative_to(d)) for p in d.rglob("*")) == before


@pytest.mark.skipif(HELM is None, reason="helm not available")
def test_render_failure_is_one_error_line(tmp_path):
    d = chart(tmp_path)
    (d / "templates" / "bad.yaml").write_text("{{ fail \"boom\" }}\n", encoding="utf-8", newline="\n")
    rc, out, err = sh(RENDER, d, "r", "n")
    assert rc == 1 and out == "" and err.startswith("error:") and err.count("\n") == 1


def test_scripts_are_executable_bash_with_strict_mode():
    for rel in ("scripts/helm_deps.sh", "scripts/render_chart.sh"):
        text = (ROOT / rel).read_bytes().decode("utf-8")
        assert text.startswith("#!/usr/bin/env bash\n") and "\r" not in text, rel
        assert "set -euo pipefail" in text, rel
        if (ROOT / ".git").exists():
            ls = subprocess.run(["git", "ls-files", "-s", rel], cwd=ROOT, capture_output=True, text=True).stdout
            assert ls.startswith("100755"), (rel, ls)


@pytest.mark.skipif(HELM is None or os.environ.get("PLUGIN_TEST_NETWORK") != "1",
                    reason="set PLUGIN_TEST_NETWORK=1 to run (needs network)")
def test_network_wrapper_chart_renders_with_empty_repo_config(tmp_path):
    d = chart(tmp_path, """dependencies:
  - {name: podinfo, version: 6.7.1, repository: "https://stefanprodan.github.io/podinfo"}
""", name="podinfo")
    env = {"HELM_REPOSITORY_CONFIG": str(tmp_path / "empty.yaml"), "HELM_REPOSITORY_CACHE": str(tmp_path / "cache")}
    (tmp_path / "empty.yaml").write_text("", encoding="utf-8")
    rc, out, err = sh(RENDER, d, "podinfo", "podinfo", env=env)
    assert rc == 0, err
    assert "name: podinfo" in out
    assert not (d / "charts").exists() and not (d / "Chart.lock").exists()
