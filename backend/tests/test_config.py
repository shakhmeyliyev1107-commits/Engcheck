from engcheck.config import get_settings


def test_service_binds_to_loopback_only(tmp_path, monkeypatch):
    monkeypatch.setenv("ENGCHECK_DATA_DIR", str(tmp_path / "d"))
    s = get_settings()
    assert s.host == "127.0.0.1" and (tmp_path / "d").is_dir()
    assert s.db_url.endswith("engcheck.db")
