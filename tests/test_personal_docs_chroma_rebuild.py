"""Tests for PersonalDocsManager's Chroma disaster-recovery path (Workstream
J: "Chroma rebuild from authoritative state"). `rag_manager.rebuild_index()`
only wipes the vector collection; `index_all_directories()` (repopulation
from `indexed_directories.json`, the actual authoritative source of truth)
existed but had zero callers and zero tests before this. Covers both
`index_all_directories()` itself and the new
`rebuild_index_from_authoritative_state()` orchestration.
"""
from src.personal_docs import PersonalDocsManager


class _FakeRagManager:
    def __init__(self, rebuild_result=True, index_results=None):
        self._rebuild_result = rebuild_result
        self._index_results = index_results or {}
        self.rebuild_calls = 0
        self.indexed_dirs = []

    def rebuild_index(self):
        self.rebuild_calls += 1
        return self._rebuild_result

    def index_personal_documents(self, directory, owner=None, file_extensions=None):
        self.indexed_dirs.append(directory)
        return self._index_results.get(directory, {"success": True, "indexed_count": 1})


def test_index_all_directories_indexes_base_and_tracked_dirs(tmp_path):
    extra = tmp_path / "extra"
    extra.mkdir()
    rag = _FakeRagManager()
    manager = PersonalDocsManager(str(tmp_path), rag_manager=rag)
    manager.indexed_directories = [str(extra)]

    result = manager.index_all_directories()

    assert result == {"success": 2, "failed": 0}
    assert str(tmp_path) in rag.indexed_dirs
    assert str(extra) in rag.indexed_dirs


def test_index_all_directories_skips_missing_directory_without_crashing(tmp_path):
    rag = _FakeRagManager()
    manager = PersonalDocsManager(str(tmp_path), rag_manager=rag)
    manager.indexed_directories = [str(tmp_path / "does-not-exist")]

    result = manager.index_all_directories()

    assert result["failed"] == 1
    assert str(tmp_path / "does-not-exist") not in rag.indexed_dirs


def test_index_all_directories_counts_reported_index_failure(tmp_path):
    extra = tmp_path / "extra"
    extra.mkdir()
    rag = _FakeRagManager(index_results={str(extra): {"success": False, "message": "boom"}})
    manager = PersonalDocsManager(str(tmp_path), rag_manager=rag)
    manager.indexed_directories = [str(extra)]

    result = manager.index_all_directories()

    assert result["failed"] == 1
    assert result["success"] == 1  # base directory still indexed fine


def test_index_all_directories_no_rag_manager_is_a_noop():
    manager = PersonalDocsManager.__new__(PersonalDocsManager)
    manager.rag_manager = None
    manager.personal_dir = "/tmp/irrelevant"
    manager.indexed_directories = []

    assert manager.index_all_directories() is None


def test_rebuild_from_authoritative_state_wipes_then_repopulates(tmp_path):
    extra = tmp_path / "extra"
    extra.mkdir()
    rag = _FakeRagManager()
    manager = PersonalDocsManager(str(tmp_path), rag_manager=rag)
    manager.indexed_directories = [str(extra)]

    result = manager.rebuild_index_from_authoritative_state()

    assert rag.rebuild_calls == 1
    assert result["wiped"] is True
    assert result["reindexed"] == {"success": 2, "failed": 0}


def test_rebuild_from_authoritative_state_reports_wipe_failure_and_does_not_repopulate(tmp_path):
    rag = _FakeRagManager(rebuild_result=False)
    manager = PersonalDocsManager(str(tmp_path), rag_manager=rag)

    result = manager.rebuild_index_from_authoritative_state()

    assert result["wiped"] is False
    assert result["reindexed"] is None
    assert result["error"]
    assert rag.indexed_dirs == []  # never repopulated after a failed wipe


def test_rebuild_from_authoritative_state_reports_wipe_exception(tmp_path):
    class _ExplodingRag(_FakeRagManager):
        def rebuild_index(self):
            raise RuntimeError("chroma unreachable")

    manager = PersonalDocsManager(str(tmp_path), rag_manager=_ExplodingRag())

    result = manager.rebuild_index_from_authoritative_state()

    assert result["wiped"] is False
    assert "chroma unreachable" in result["error"]


def test_rebuild_from_authoritative_state_without_rag_manager_reports_truthfully(tmp_path):
    manager = PersonalDocsManager(str(tmp_path), rag_manager=None)

    result = manager.rebuild_index_from_authoritative_state()

    assert result == {"wiped": False, "reindexed": None, "error": "no RAG manager available"}
