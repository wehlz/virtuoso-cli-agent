import yaml

from core.profiles import PROFILE_SETTINGS, apply_profile


def test_apply_profile_cloud(tmp_path, monkeypatch):
    cfg_path = tmp_path / "virtuoso.yaml"
    cfg_path.write_text("llm:\n  backend: shimmy\n", encoding="utf-8")
    monkeypatch.setattr("core.profiles.CONFIG_PATH", cfg_path)

    apply_profile("cloud", persist=True)
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert data["llm"]["backend"] == PROFILE_SETTINGS["cloud"]["llm"]["backend"]
