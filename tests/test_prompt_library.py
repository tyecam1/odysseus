import pytest

from src import prompt_library as lib


@pytest.fixture
def libdir(tmp_path, monkeypatch):
    monkeypatch.setattr(lib, "LIB", tmp_path / "lib")
    monkeypatch.setenv("ODYSSEUS_DATA_DIR", str(tmp_path / "data"))
    d = tmp_path / "lib" / "demo" / "x"
    d.mkdir(parents=True)
    (d / "v1.md").write_text("---\nid: demo/x\nversion: 1\nparent: 0\nreason: seed\n---\nExtract things.\n")
    (d / "CURRENT").write_text("1\n")
    return "demo/x"


def test_get_returns_text_and_version(libdir):
    assert lib.get(libdir) == ("Extract things.", 1)


def test_child_is_immutable_and_not_current_until_it_beats_parent(libdir):
    n = lib.register_child(libdir, "Extract durable things.", parent=1, reason="tighten scope")
    assert n == 2 and lib.current_version(libdir) == 1
    lib.record(libdir, 1, total=100, ok=70)
    assert lib.promote(libdir, 2) is False                     # no evidence yet
    lib.record(libdir, 2, total=100, ok=60)
    assert lib.promote(libdir, 2) is False and lib.current_version(libdir) == 1
    lib.record(libdir, 2, total=100, ok=90)
    assert lib.promote(libdir, 2) is True and lib.current_version(libdir) == 2


def test_register_child_needs_reason_and_known_parent(libdir):
    with pytest.raises(ValueError):
        lib.register_child(libdir, "x", parent=9, reason="r")
    with pytest.raises(ValueError):
        lib.register_child(libdir, "x", parent=1, reason=" ")


def test_improvement_report_flags_high_rejection(libdir):
    lib.record(libdir, 1, total=50, ok=20, rejected=25)
    assert lib.improvement_report()[libdir]["weak"] == {"rejected": 0.5}


def test_chatgpt_prompts_come_from_the_library():
    from src import chatgpt_ingest as ci
    assert ci.EXTRACT_SYSTEM == lib.text("chatgpt/extract") and ci.PROMPT_VERSION == f"v{lib.current_version('chatgpt/extract')}"
