import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/render_template.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_renders_all_keys_lf_utf8_no_bom(tmp_path):
    tpl = tmp_path / "a.tmpl"; tpl.write_text("x: {{ A }}\ny: {{ B }}\n", encoding="utf-8")
    out = tmp_path / "a.yaml"
    p = run(str(tpl), str(out), "A=1", "B=two")
    assert p.returncode == 0, p.stderr
    raw = out.read_bytes()
    assert raw == b"x: 1\ny: two\n" and not raw.startswith(b"\xef\xbb\xbf")


def test_missing_value_is_an_error_and_writes_nothing(tmp_path):
    tpl = tmp_path / "a.tmpl"; tpl.write_text("{{ A }} {{ B }}", encoding="utf-8")
    out = tmp_path / "a.out"
    p = run(str(tpl), str(out), "A=1")
    assert p.returncode == 1 and p.stderr.strip() == "error: no value for: B" and not out.exists()


def test_unused_value_is_an_error(tmp_path):
    tpl = tmp_path / "a.tmpl"; tpl.write_text("{{ A }}", encoding="utf-8")
    p = run(str(tpl), str(tmp_path / "o"), "A=1", "TYPO=2")
    assert p.returncode == 1 and "TYPO" in p.stderr


def test_crlf_template_is_written_lf(tmp_path):
    tpl = tmp_path / "a.tmpl"; tpl.write_bytes(b"a: {{ A }}\r\nb: 2\r\n")
    out = tmp_path / "o"
    assert run(str(tpl), str(out), "A=1").returncode == 0
    assert out.read_bytes() == b"a: 1\nb: 2\n"


def test_non_placeholder_braces_are_left_alone(tmp_path):
    tpl = tmp_path / "a.tmpl"
    tpl.write_text("{{ .Values.x }} {{ lower }} {{ A }}\n", encoding="utf-8")
    out = tmp_path / "o"
    assert run(str(tpl), str(out), "A=1").returncode == 0
    assert out.read_text(encoding="utf-8") == "{{ .Values.x }} {{ lower }} 1\n"


def test_value_containing_equals_and_non_ascii(tmp_path):
    tpl = tmp_path / "a.tmpl"; tpl.write_text("{{ A }}", encoding="utf-8")
    out = tmp_path / "o"
    assert run(str(tpl), str(out), "A=k=v ≥").returncode == 0
    assert out.read_bytes() == "k=v ≥".encode("utf-8")


def _one_line_error(p):
    assert p.returncode == 1 and p.stderr.startswith("error:") and "Traceback" not in p.stderr


def test_missing_template_is_a_one_line_error(tmp_path):
    _one_line_error(run(str(tmp_path / "nope.tmpl"), str(tmp_path / "o"), "A=1"))


def test_non_utf8_template_is_a_one_line_error(tmp_path):
    tpl = tmp_path / "a.tmpl"; tpl.write_bytes(bytes([0xFF, 0xFE]) + b"{{ A }}")
    _one_line_error(run(str(tpl), str(tmp_path / "o"), "A=1"))


def test_output_path_is_a_directory_is_a_one_line_error(tmp_path):
    tpl = tmp_path / "a.tmpl"; tpl.write_text("{{ A }}", encoding="utf-8")
    d = tmp_path / "dir"; d.mkdir()
    _one_line_error(run(str(tpl), str(d), "A=1"))
    assert not list(tmp_path.glob("*.tmp")) and not list(d.glob("*.tmp"))


def test_output_parent_is_a_file_is_a_one_line_error(tmp_path):
    tpl = tmp_path / "a.tmpl"; tpl.write_text("{{ A }}", encoding="utf-8")
    f = tmp_path / "f"; f.write_text("x")
    _one_line_error(run(str(tpl), str(f / "o"), "A=1"))


def test_duplicate_key_is_rejected(tmp_path):
    tpl = tmp_path / "a.tmpl"; tpl.write_text("{{ A }}", encoding="utf-8")
    out = tmp_path / "o"
    p = run(str(tpl), str(out), "A=1", "A=2")
    assert p.returncode == 2 and "A" in p.stderr and not out.exists()


def test_values_with_regex_special_characters_are_literal(tmp_path):
    tpl = tmp_path / "a.tmpl"; tpl.write_text("{{ A }}", encoding="utf-8")
    out = tmp_path / "o"
    value = "a\\1 & $1 \\g<0>"
    assert run(str(tpl), str(out), "A=" + value).returncode == 0
    assert out.read_text(encoding="utf-8") == value
