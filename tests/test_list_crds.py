"""scripts/list_crds.sh --filter: CRD names from rendered YAML, no helm or network needed."""
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "list_crds.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="bash not available")


def run_filter(text):
    p = subprocess.run([BASH, SCRIPT.as_posix(), "--filter"], input=text.encode("utf-8"),
                       capture_output=True)
    return p.returncode, p.stdout.decode("utf-8")


CRD = """---
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  annotations:
    a: b
  name: {name}
spec:
  group: example.com
  names:
    kind: Thing
    name: not-a-crd-name
  versions:
    - name: v1
"""


def test_two_crds_and_configmap_sorted():
    text = (CRD.format(name="zeta.example.com") + CRD.format(name="alpha.example.com")
            + "---\napiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: cm\n")
    assert run_filter(text) == (0, "alpha.example.com\nzeta.example.com\n")


def test_crlf_input_has_clean_names():
    text = (CRD.format(name="a.example.com") + CRD.format(name="b.example.com")).replace("\n", "\r\n")
    rc, out = run_filter(text)
    assert rc == 0 and out == "a.example.com\nb.example.com\n"


def test_nested_names_and_mentions_not_taken():
    text = (CRD.format(name="real.example.com")
            + "---\napiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: cm\ndata:\n"
              "  note: |\n    kind: CustomResourceDefinition\n"
              "# kind: CustomResourceDefinition\n")
    assert run_filter(text) == (0, "real.example.com\n")


def test_metadata_before_kind_and_duplicates():
    doc = "---\nmetadata:\n  name: x.example.com\nkind: CustomResourceDefinition\n"
    assert run_filter(doc + doc) == (0, "x.example.com\n")


def test_empty_input():
    assert run_filter("") == (0, "")


def test_non_crd_render_is_empty():
    text = "---\nkind: Deployment\nmetadata:\n  name: d\nspec:\n  template:\n    spec:\n      containers:\n      - name: c\n"
    assert run_filter(text) == (0, "")


def test_script_header_and_mode():
    s = SCRIPT.read_text(encoding="utf-8")
    assert s.startswith("#!/usr/bin/env bash") and "set -euo pipefail" in s and "\r" not in s
    out = subprocess.run(["git", "ls-files", "-s", "scripts/list_crds.sh"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    if out:
        assert out.startswith("100755"), out
