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


# --- Task 5 (F5): atomic --out, bare-uid variables, --labels/--relabel, LF ---
BARE = ROOT / "tests/fixtures/raw-dashboard-bare-uid.json"


def _cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True)


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


def test_bare_string_datasource_on_template_variables_is_rewritten():
    out = json.loads(_run(BARE).stdout)
    by_name = {v["name"]: v for v in out["templating"]["list"]}
    assert by_name["namespace"]["datasource"] == "${datasource}"
    assert by_name["pod"]["datasource"] == "${datasource}"


def test_variable_datasource_dict_still_handled_and_builtins_kept(tmp_path):
    src = _write(tmp_path / "d.json", {"title": "t", "templating": {"list": [
        {"name": "a", "type": "query", "datasource": {"type": "prometheus", "uid": "abc"}, "query": "x"},
        {"name": "b", "type": "query", "datasource": "-- Mixed --", "query": "x"},
        {"name": "c", "type": "query", "datasource": "Grafana", "query": "x"},
        {"name": "d", "type": "custom", "datasource": "beok", "query": "x"},
    ]}, "panels": [{"datasource": "prometheus", "targets": []}]})
    by = {v["name"]: v for v in json.loads(_cli(src).stdout)["templating"]["list"]}
    assert by["a"]["datasource"] == {"type": "prometheus", "uid": "${datasource}"}
    assert by["b"]["datasource"] == "-- Mixed --"
    assert by["c"]["datasource"] == "Grafana"
    assert by["d"]["datasource"] == "beok"          # only type=query variables are rewritten


def test_bare_uid_rewrite_counts_as_a_prometheus_reference(tmp_path):
    src = _write(tmp_path / "d.json", {"title": "t", "templating": {"list": [
        {"name": "n", "type": "query", "datasource": "beok", "query": "x"}]}})
    assert _cli(src).returncode == 0


def test_non_prom_input_name_variable_is_left_alone(tmp_path):
    src = _write(tmp_path / "d.json", {
        "title": "t",
        "__inputs": [{"name": "DS_LOKI", "type": "datasource", "pluginId": "loki"}],
        "templating": {"list": [{"name": "n", "type": "query", "datasource": "DS_LOKI", "query": "x"}]},
        "panels": [{"datasource": "prometheus", "targets": []}]})
    by = {v["name"]: v for v in json.loads(_cli(src).stdout)["templating"]["list"]}
    assert by["n"]["datasource"] == "DS_LOKI"


def test_out_flag_writes_atomically_and_leaves_nothing_on_failure(tmp_path):
    good = tmp_path / "good.json"
    p = _cli(FIXTURE, "--out", good)
    assert p.returncode == 0 and json.loads(good.read_text(encoding="utf-8"))["title"]
    assert b"\r\n" not in good.read_bytes()            # LF only, even on Windows
    bad = tmp_path / "bad.json"
    p = _cli(tmp_path / "missing.json", "--out", bad)
    assert p.returncode == 1 and not bad.exists()       # no zero-byte poison file
    assert not list(tmp_path.glob("*.tmp"))


def test_out_flag_leaves_nothing_when_normalization_fails(tmp_path):
    src = _write(tmp_path / "loki.json", {"title": "x", "panels": [
        {"id": 1, "datasource": {"type": "loki", "uid": "l1"}}]})
    out = tmp_path / "out.json"
    p = _cli(src, "--out", out)
    assert p.returncode == 1 and "Prometheus" in p.stderr
    assert not out.exists() and not list(tmp_path.glob("*.tmp"))


def test_out_flag_failure_does_not_touch_existing_target(tmp_path):
    out = tmp_path / "keep.json"
    out.write_text("precious", encoding="utf-8")
    assert _cli(tmp_path / "missing.json", "--out", out).returncode == 1
    assert out.read_text(encoding="utf-8") == "precious"


def test_out_into_missing_directory_fails_cleanly(tmp_path):
    out = tmp_path / "nope" / "d.json"
    p = _cli(FIXTURE, "--out", out)
    assert p.returncode == 1 and "Traceback" not in p.stderr and "does not exist" in p.stderr
    assert not (tmp_path / "nope").exists()


def test_stdout_is_lf_only_as_raw_bytes():
    p = subprocess.run([sys.executable, str(SCRIPT), str(FIXTURE)], capture_output=True)
    assert p.returncode == 0 and b"\r\n" not in p.stdout and p.stdout.endswith(b"}\n")


def test_local_source_records_basename_not_absolute_path():
    out = json.loads(_run(FIXTURE).stdout)
    assert str(ROOT) not in out["__source"]
    assert out["__source"].startswith("raw-dashboard.json, fetched ")


def _load_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("fd", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_source_label_for_url_grafana_com_and_windows_path():
    fd = _load_module()

    def src(origin):
        return fd.normalize({"panels": [{"datasource": "prometheus"}]}, origin)["__source"]

    url = "https://example.com/some/dash.json"
    gcom = "grafana.com/dashboards/1860 revision 3"
    assert src(url).startswith(url + ", fetched ")
    assert src(gcom).startswith(gcom + ", fetched ")
    assert src(r"C:\some\dir\dash.json").startswith("dash.json, fetched ")
    assert src("/home/u/dash.json").startswith("dash.json, fetched ")


def test_labels_flag_lists_label_names_used_in_queries():
    p = _cli(BARE, "--labels")
    assert p.returncode == 0
    assert set(json.loads(p.stdout)) == {"kubernetes_namespace", "kubernetes_pod_name"}


def test_labels_ignores_string_literals_outside_matchers(tmp_path):
    src = _write(tmp_path / "d.json", {"title": "t", "panels": [{"datasource": "prometheus", "targets": [
        {"expr": 'label_replace(up{job="x"}, "foo", "$1", "bar", "(.*)")'}]}]})
    assert json.loads(_cli(src, "--labels").stdout) == ["job"]


def test_relabel_rewrites_queries_and_variable_definitions():
    p = _cli(BARE, "--relabel", "kubernetes_namespace=namespace",
             "--relabel", "kubernetes_pod_name=pod")
    assert p.returncode == 0
    text = p.stdout
    assert "kubernetes_namespace" not in text and "kubernetes_pod_name" not in text
    assert 'namespace=~\\"$namespace\\"' in text


def test_relabel_respects_identifier_boundaries_and_only_touches_query_and_legend_keys(tmp_path):
    src = _write(tmp_path / "d.json", {"title": "kubernetes_namespace", "panels": [{
        "datasource": "prometheus",
        "targets": [{"expr": 'up{kubernetes_namespace="a", kubernetes_namespace_foo="b", x_kubernetes_namespace="c"}',
                     "legendFormat": "{{kubernetes_namespace}}"}]}]})
    out = json.loads(_cli(src, "--relabel", "kubernetes_namespace=namespace").stdout)
    t = out["panels"][0]["targets"][0]
    assert t["expr"] == 'up{namespace="a", kubernetes_namespace_foo="b", x_kubernetes_namespace="c"}'
    assert t["legendFormat"] == "{{namespace}}"      # legend templates are relabelled too (review round)
    assert out["title"] == "kubernetes_namespace"


def test_args_order_and_errors():
    assert _cli("--labels", BARE).returncode == 0                # flag before source
    assert _cli(BARE, "--relabel", "noequals").returncode == 2   # malformed
    assert _cli(BARE, "--relabel", "=x").returncode == 2         # empty old name
    assert _cli(BARE, "--bogus").returncode == 2                 # unknown flag
    assert _cli(BARE, "--out").returncode == 2                   # missing value
    assert _cli().returncode == 2                                # no source


# --- review round: shared label scanner, legends, ASCII stderr ---
def _dash_with(tmp_path, expr=None, legend=None, extra_target=None):
    tgt = {}
    if expr is not None:
        tgt["expr"] = expr
    if legend is not None:
        tgt["legendFormat"] = legend
    return _write(tmp_path / "s.json", {"title": "t", "panels": [
        {"datasource": "prometheus", "targets": [tgt]}]})


def _relabelled(tmp_path, expr=None, legend=None, mapping="kubernetes_pod_name=pod"):
    out = json.loads(_cli(_dash_with(tmp_path, expr, legend), "--relabel", mapping).stdout)
    return out["panels"][0]["targets"][0]


def _labels(tmp_path, expr):
    return json.loads(_cli(_dash_with(tmp_path, expr), "--labels").stdout)


def test_legend_template_labels_are_relabelled_only_inside_braces(tmp_path):
    t = _relabelled(tmp_path, "up", "{{kubernetes_pod_name}} and {{ kubernetes_pod_name }} kubernetes_pod_name")
    assert t["legendFormat"] == "{{pod}} and {{ pod }} kubernetes_pod_name"
    t = _relabelled(tmp_path, "up", "x {pod={{kubernetes_pod_name}}}")
    assert t["legendFormat"] == "x {pod={{pod}}}"


def test_legend_labels_are_reported(tmp_path):
    src = _dash_with(tmp_path, "up", "{{ kubernetes_pod_name }}")
    assert json.loads(_cli(src, "--labels").stdout) == ["kubernetes_pod_name"]


def test_nested_brace_regex_does_not_hide_matchers(tmp_path):
    expr = 'up{a=~"x{2}", kubernetes_pod_name="p"}'
    assert _labels(tmp_path, expr) == ["a", "kubernetes_pod_name"]
    assert _relabelled(tmp_path, expr)["expr"] == 'up{a=~"x{2}", pod="p"}'


def test_grouping_and_matching_clauses_are_reported_and_rewritten(tmp_path):
    cases = {
        "sum by (kubernetes_pod_name, job) (up)": "sum by (pod, job) (up)",
        "sum without(kubernetes_pod_name) (up)": "sum without(pod) (up)",
        "a / on(kubernetes_pod_name) group_left(kubernetes_pod_name) b":
            "a / on(pod) group_left(pod) b",
        "a / ignoring (kubernetes_pod_name) group_right () b": "a / ignoring (pod) group_right () b",
    }
    for expr, want in cases.items():
        assert "kubernetes_pod_name" in _labels(tmp_path, expr), expr
        assert _relabelled(tmp_path, expr)["expr"] == want


def test_string_values_metrics_and_label_replace_args_are_left_alone(tmp_path):
    expr = 'up{pod="kubernetes_pod_name"}'
    assert _labels(tmp_path, expr) == ["pod"]
    assert _relabelled(tmp_path, expr)["expr"] == expr
    expr = "label_values(kubernetes_pod_name)"       # a metric literally named like the label
    assert _labels(tmp_path, expr) == []
    assert _relabelled(tmp_path, expr)["expr"] == expr
    expr = 'label_replace(up, "kubernetes_pod_name", "$1", "x", "(.*)")'
    assert _relabelled(tmp_path, expr)["expr"] == expr
    expr = "kubernetes_pod_name{job=\"j\"}"
    assert _relabelled(tmp_path, expr)["expr"] == expr


def test_label_values_last_argument_is_a_label(tmp_path):
    expr = 'label_values(up{a="1",b="2"}, kubernetes_pod_name)'
    assert _labels(tmp_path, expr) == ["a", "b", "kubernetes_pod_name"]
    assert _relabelled(tmp_path, expr)["expr"] == 'label_values(up{a="1",b="2"}, pod)'


def test_escaped_quotes_in_strings_are_masked(tmp_path):
    expr = 'up{a="x\\"}, kubernetes_pod_name=\\"", kubernetes_pod_name="y"}'
    assert _labels(tmp_path, expr) == ["a", "kubernetes_pod_name"]


def test_labels_after_relabel_no_longer_list_old_names(tmp_path):
    out = tmp_path / "o.json"
    assert _cli(BARE, "--relabel", "kubernetes_namespace=namespace",
                "--relabel", "kubernetes_pod_name=pod", "--out", out).returncode == 0
    labels = set(json.loads(_cli(out, "--labels").stdout))
    assert labels == {"namespace", "pod"}


def test_no_prometheus_error_is_plain_ascii(tmp_path):
    src = _write(tmp_path / "loki.json", {"title": "x", "panels": [
        {"datasource": {"type": "loki", "uid": "l"}}]})
    p = subprocess.run([sys.executable, str(SCRIPT), str(src)], capture_output=True)
    assert p.returncode == 1 and p.stderr.decode("ascii")
