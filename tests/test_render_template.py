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
    assert p.returncode == 1 and "B" in p.stderr and not out.exists()


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
