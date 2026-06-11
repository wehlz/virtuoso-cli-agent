import virtuoso as cli


def test_version_flag_outputs_version(capsys):
    original_parse_args = cli.parse_args
    try:
        cli.parse_args = lambda: type(
            "Args",
            (),
            {
                "version": True,
                "doctor": False,
                "serve": False,
                "dashboard": False,
                "tui": False,
            },
        )()
        cli.cli_main()
        out = capsys.readouterr().out
        assert "virtuoso 1.0.0" in out
    finally:
        cli.parse_args = original_parse_args


def test_doctor_returns_success_with_optional_warnings(monkeypatch, tmp_path, capsys):
    cfg_path = tmp_path / "virtuoso.yaml"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("core.config._config_path", lambda: cfg_path)
    monkeypatch.setattr("core.paths.config_path", lambda: cfg_path)
    monkeypatch.setattr("virtuoso.has_ripgrep", lambda: False)
    monkeypatch.setattr("core.web_dashboard._dashboard_html_path", lambda: tmp_path / "dashboard.html")
    monkeypatch.setattr("core.web_dashboard._logo_path", lambda: tmp_path / "virtuoso.ico")
    (tmp_path / "dashboard.html").write_text("<html>Virtuoso</html>", encoding="utf-8")
    (tmp_path / "virtuoso.ico").write_bytes(b"\x00\x00\x01\x00\x01\x00")

    rc = cli.cmd_doctor()
    out = capsys.readouterr().out

    assert rc == 0
    assert "Virtuoso doctor" in out
    assert "Config file" in out
