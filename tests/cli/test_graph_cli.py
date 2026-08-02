from __future__ import annotations

import json
import shutil
from pathlib import Path

from tests.helpers.cli_loader import load_script


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "capability_graph" / "sources"


def test_graph_cli_build_check_query_export_and_explain(tmp_path, capsys):
    source = tmp_path / "sources"
    shutil.copytree(FIXTURE_ROOT, source)
    db = tmp_path / "graph.db"
    exported = tmp_path / "graph.json"
    cli = load_script("odysseus-graph")

    assert cli.main(["build", "--sources", str(source), "--out", str(db)]) == 0
    build_output = json.loads(capsys.readouterr().out)
    assert build_output["nodes"]["total"] > 0

    assert cli.main(["check", "--db", str(db), "--sources", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["freshness"] == "current"

    assert cli.main(["query", "--db", str(db), "what-should-handle", "--route", "task-class:demo", "--json"]) == 0
    query_output = json.loads(capsys.readouterr().out)
    assert query_output["result"]["handlers"][0]["id"] == "action:2026-08-02-demo"

    assert cli.main(["explain", "--db", str(db), "--route", "task-class:demo"]) == 0
    explain_output = json.loads(capsys.readouterr().out)
    assert explain_output["result"]["paths"][0]["edges"][0]["provenance"]

    assert cli.main(["export", "--db", str(db), "--out", str(exported)]) == 0
    export_output = json.loads(capsys.readouterr().out)
    assert export_output["sha256"]
    assert exported.exists()
    assert exported.with_name("graph.json.metadata.json").exists()
