"""fetch_dashboard.py: local-file input + datasource normalization. No network."""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py"
FIXTURE = ROOT / "tests/fixtures/raw-dashboard.json"


def _run(arg):
    p = subprocess.run(
        [sys.executable, str(SCRIPT), str(arg)],
        capture_output=True, text=True,
    )
    return p


def test_script_exists():
    assert SCRIPT.exists()


def test_normalizes_local_fixture_to_valid_json():
    p = _run(FIXTURE)
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)  # raises if not valid JSON
    assert out["title"] == "Test App Overview"


def test_strips_import_metadata():
    out = json.loads(_run(FIXTURE).stdout)
    for k in ("__inputs", "__requires", "id", "uid"):
        assert k not in out, k


def test_adds_datasource_template_var():
    out = json.loads(_run(FIXTURE).stdout)
    names = [v.get("name") for v in out["templating"]["list"]]
    assert "datasource" in names
    dsv = next(v for v in out["templating"]["list"] if v["name"] == "datasource")
    assert dsv["type"] == "datasource" and dsv["query"] == "prometheus"


def test_no_ds_input_placeholders_remain():
    assert "${DS_" not in _run(FIXTURE).stdout


def test_legacy_string_datasource_rewritten():
    out = json.loads(_run(FIXTURE).stdout)
    panel = next(p for p in out["panels"] if p["id"] == 1)
    assert panel["datasource"] == "${datasource}"
    assert panel["targets"][0]["datasource"] == "${datasource}"


def test_modern_object_datasource_rewritten():
    out = json.loads(_run(FIXTURE).stdout)
    panel = next(p for p in out["panels"] if p["id"] == 2)
    assert panel["datasource"] == {"type": "prometheus", "uid": "${datasource}"}
    assert panel["targets"][0]["datasource"] == {"type": "prometheus", "uid": "${datasource}"}


def test_null_datasource_left_alone():
    out = json.loads(_run(FIXTURE).stdout)
    panel = next(p for p in out["panels"] if p["id"] == 3)
    assert panel["datasource"] is None


def test_provenance_recorded():
    out = json.loads(_run(FIXTURE).stdout)
    assert "__source" in out and "fetched" in out["__source"]


def test_non_prometheus_dashboard_fails():
    # a dashboard with no prometheus reference at all -> non-zero exit
    tmp = ROOT / "tests/.out/no-prom.json"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(json.dumps({"title": "x", "panels": [
        {"id": 1, "type": "stat", "datasource": {"type": "loki", "uid": "l1"}}
    ]}))
    p = _run(tmp)
    assert p.returncode != 0
    tmp.unlink()
