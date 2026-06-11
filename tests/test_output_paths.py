from pathlib import Path

from core.output_paths import OutputTarget, parse_output_target, resolve_output_file, sanitize_name, write_code_output


def test_sanitize_name():
    assert sanitize_name('ai test math') == "ai test math"
    assert sanitize_name('bad:name') == "badname"


def test_parse_desktop_titled():
    target = parse_output_target("a python document on my desktop titled ai test math")
    assert target is not None
    assert target.folder_name == "ai test math"


def test_parse_explicit_save():
    target = parse_output_target("", explicit_path="C:/tmp/out.py")
    assert target is not None
    assert target.filename == "out.py"
    assert target.directory == Path("C:/tmp")


def test_resolve_output_file(tmp_path):
    target = OutputTarget(directory=tmp_path, folder_name="ai test math")
    path = resolve_output_file(target, "titled ai test math", "print('hi')\n")
    assert path.parent.name == "ai test math"
    assert path.suffix == ".py"


def test_write_code_output(tmp_path, monkeypatch):
    monkeypatch.setattr("core.output_paths.desktop_path", lambda: tmp_path)
    code = "print('fractions')\n"
    written = write_code_output(
        code,
        "basic python on my desktop titled fraction_solver",
    )
    assert written is not None
    assert written.exists()
    assert "fractions" in written.read_text(encoding="utf-8")
