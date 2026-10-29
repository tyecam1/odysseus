"""Synthetic-only read-only reader startup, HTTP and direct authority acceptance."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.runtime_profile import SOURCE_ALIASES, ESTATE_ROOT_ALIASES, WRITABLE_OVERRIDES, runtime_profile


REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def sources(tmp_path):
    roots = {}
    for profile, directory, title in (
        ("misumi-reader", "agent-tasks/inbox", "OWN_MISUMI_CANARY"),
        ("phd-reader", "10-inbox", "OWN_PHD_CANARY"),
    ):
        root = tmp_path / profile
        subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
        target = root / directory
        target.mkdir(parents=True)
        (target / "own.md").write_text(f"---\nartifact_type: work-item\nstatus: open\n---\n# {title}\n", encoding="utf-8")
        roots[profile] = root
    # Static foreign canary via a symlink, not an actual foreign domain write.
    for profile, root in roots.items():
        other = roots["phd-reader" if profile == "misumi-reader" else "misumi-reader"]
        directory = "agent-tasks/inbox" if profile == "misumi-reader" else "10-inbox"
        other_directory = "10-inbox" if profile == "misumi-reader" else "agent-tasks/inbox"
        (root / directory / "escape.md").symlink_to(other / other_directory / "own.md")
    return roots


def reader_env(tmp_path, sources, profile="misumi-reader"):
    env = os.environ.copy()
    for key in ("DATABASE_URL", "ODYSSEUS_DATA_DIR", *WRITABLE_OVERRIDES, *(key for aliases in (*SOURCE_ALIASES.values(), *ESTATE_ROOT_ALIASES.values()) for key in aliases)):
        env.pop(key, None)
    own = "BBC_MISUMI_ROOT" if profile == "misumi-reader" else "BBC_OBSIDIAN_PHD_ROOT"
    env.update(ODYSSEUS_RUNTIME_PROFILE=profile, ODYSSEUS_DATA_DIR=str(tmp_path / "private-data"), AUTH_ENABLED="true", LOCALHOST_BYPASS="false", PYTHONDONTWRITEBYTECODE="1", **{own: str(sources[profile])})
    return env


@pytest.mark.parametrize("profile", ["misumi-reader", "phd-reader"])
def test_real_reader_app_and_restart(tmp_path, sources, profile):
    env = reader_env(tmp_path, sources, profile)
    source_before = {str(p): p.read_bytes() for root in sources.values() for p in root.rglob("*.md")}
    evidence = []
    for _ in range(2):
        run = subprocess.run([sys.executable, "-B", str(REPO / "tests/fixtures/domain_reader_probe.py")], cwd=REPO, env=env, capture_output=True, text=True, timeout=45)
        assert run.returncode == 0, run.stdout + run.stderr
        result = json.loads(next(line.removeprefix("READER_EVIDENCE=") for line in run.stdout.splitlines() if line.startswith("READER_EVIDENCE=")))
        evidence.append(result)
        assert result["authority_rows"] == result["startup_jobs"] == 0
        assert result["direct_refusals"] > 200
    assert evidence[0]["direct_refusals"] == evidence[1]["direct_refusals"]
    assert source_before == {str(p): p.read_bytes() for root in sources.values() for p in root.rglob("*.md")}
    print(json.dumps(evidence))


@pytest.mark.parametrize("case", [
    "missing-data", "relative-data", "missing-source", "relative-source", "bad-source",
    "source-overlap", "data-alias", "descendant-alias", "mail-escape", "embed-escape",
    "data-override-escape", "case-override-escape", "empty-mail", "source-conflict", "no-auth", "bypass", "unknown-profile", "joint-default",
    *[f"foreign:{key}" for key in (*SOURCE_ALIASES["obsidian-phd"], *SOURCE_ALIASES["odysseus"], *ESTATE_ROOT_ALIASES["obsidian-phd"], *ESTATE_ROOT_ALIASES["odysseus"])],
    *[f"database:{value}" for value in ("", "sqlite:///:memory:", "sqlite:////tmp/shared.db", "postgresql://secret:private@example.invalid/shared")],
])
def test_real_app_rejects_before_state_writes(tmp_path, sources, case):
    env = reader_env(tmp_path, sources)
    data = Path(env["ODYSSEUS_DATA_DIR"])
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "canary"
    marker.write_text("UNCHANGED")
    if case == "missing-data": env.pop("ODYSSEUS_DATA_DIR")
    elif case == "relative-data": env["ODYSSEUS_DATA_DIR"] = "reader-relative-forbidden"
    elif case == "missing-source": env.pop("BBC_MISUMI_ROOT")
    elif case == "relative-source": env["BBC_MISUMI_ROOT"] = "relative-source"
    elif case == "bad-source": env["BBC_MISUMI_ROOT"] = str(outside)
    elif case == "source-overlap": env["ODYSSEUS_DATA_DIR"] = str(sources["misumi-reader"] / "private")
    elif case == "data-alias": data.symlink_to(outside, target_is_directory=True)
    elif case == "descendant-alias":
        data.mkdir(); (data / "logs").symlink_to(outside, target_is_directory=True)
    elif case == "mail-escape": env["ODYSSEUS_MAIL_ATTACHMENTS_DIR"] = str(outside)
    elif case == "embed-escape": env["FASTEMBED_CACHE_PATH"] = str(outside)
    elif case == "data-override-escape": env["DATA_SESSIONS_FILE"] = str(outside / "sessions.json")
    elif case == "case-override-escape": env["data_sessions_file"] = str(outside / "sessions.json")
    elif case == "empty-mail": env["ODYSSEUS_MAIL_ATTACHMENTS_DIR"] = ""
    elif case == "source-conflict": env["MISUMI_SOURCE_ROOT"] = str(sources["phd-reader"])
    elif case == "no-auth": env["AUTH_ENABLED"] = "false"
    elif case == "bypass": env["LOCALHOST_BYPASS"] = "true"
    elif case == "unknown-profile": env["ODYSSEUS_RUNTIME_PROFILE"] = "typo"
    elif case == "joint-default": env["ODYSSEUS_DATA_DIR"] = str(REPO / "data")
    elif case.startswith("foreign:"): env[case.split(":", 1)[1]] = str(sources["phd-reader"])
    elif case.startswith("database:"): env["DATABASE_URL"] = case.split(":", 1)[1]
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    run = subprocess.run([sys.executable, "-B", "-c", "import app"], cwd=REPO, env=env, capture_output=True, text=True, timeout=20)
    assert run.returncode != 0
    assert "ReaderConfigurationError" in run.stderr, run.stderr
    assert "secret:private" not in run.stderr
    assert before == {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert not (REPO / "reader-relative-forbidden").exists()


@pytest.mark.parametrize("entrypoint", ["app", "core.database"])
@pytest.mark.parametrize("foreign", (*SOURCE_ALIASES["misumi-homebase"], *ESTATE_ROOT_ALIASES["misumi-homebase"]))
def test_phd_rejects_every_inherited_misumi_alias(tmp_path, sources, entrypoint, foreign):
    env = reader_env(tmp_path, sources, "phd-reader")
    env[foreign] = str(sources["misumi-reader"])
    run = subprocess.run([sys.executable, "-B", "-c", f"import {entrypoint}"], cwd=REPO, env=env, capture_output=True, text=True, timeout=20)
    assert run.returncode != 0 and "ReaderConfigurationError" in run.stderr, run.stderr
    assert not Path(env["ODYSSEUS_DATA_DIR"]).exists()


@pytest.mark.parametrize("setting", ["DATABASE_URL=sqlite:////tmp/shared-forbidden.db", "OBSIDIAN_PHD_ROOT=/foreign-forbidden"])
def test_dotenv_is_validated_before_core_or_log_writes(tmp_path, sources, setting):
    env = reader_env(tmp_path, sources)
    entry = tmp_path / "actual_app.py"
    entry.write_text((REPO / "app.py").read_text(), encoding="utf-8")
    (tmp_path / ".env").write_text(setting + "\n", encoding="utf-8")
    env["PYTHONPATH"] = str(REPO)
    run = subprocess.run([sys.executable, "-B", "-c", "import runpy,sys; runpy.run_path(sys.argv[1])", str(entry)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=20)
    assert run.returncode != 0 and "ReaderConfigurationError" in run.stderr, run.stderr
    assert not Path(env["ODYSSEUS_DATA_DIR"]).exists()


def test_joint_dualroot_subprocess(tmp_path, sources):
    env = reader_env(tmp_path, sources)
    odysseus = tmp_path / "joint-source"
    subprocess.run(["git", "init", "--quiet", str(odysseus)], check=True, capture_output=True)
    (odysseus / "ROADMAP.md").write_text("# Roadmap\n\n## Tests\n- OWN_JOINT_CANARY\n", encoding="utf-8")
    env.update(ODYSSEUS_RUNTIME_PROFILE="joint", BBC_ODYSSEUS_ROOT=str(odysseus), BBC_OBSIDIAN_PHD_ROOT=str(sources["phd-reader"]))
    # Remove the adversarial symlink fixture; joint's existing adapter semantics
    # are unchanged, and this test verifies the normal dual-domain configuration.
    (sources["misumi-reader"] / "agent-tasks/inbox/escape.md").unlink()
    code = """
import os
from src.bbc.runtime import build_runtime
r = build_runtime(data_dir=os.environ['ODYSSEUS_DATA_DIR'], app_root=os.environ['BBC_ODYSSEUS_ROOT'])
assert all(s.configured and s.reachable for s in r.adapters.systems())
for repo, canary in [('misumi-homebase','OWN_MISUMI_CANARY'),('obsidian-phd','OWN_PHD_CANARY'),('odysseus','OWN_JOINT_CANARY')]:
    assert canary in str(r.repository_snapshot(repo))
    assert r.invoke_capability('bbc.repository.inspect', {'repository_id':repo}, actor='fixture', caller_grants={'*'})['result']['repository_id'] == repo
print('JOINT_DUALROOT=passed')
"""
    run = subprocess.run([sys.executable, "-B", "-c", code], cwd=REPO, env=env, capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "JOINT_DUALROOT=passed" in run.stdout


def test_joint_defaults_and_wrapper_precreation_contract(tmp_path, sources):
    assert runtime_profile({}).name == "joint"
    assert not runtime_profile({"DATABASE_URL": "unchanged", "BBC_MISUMI_ROOT": "a", "BBC_OBSIDIAN_PHD_ROOT": "b"}).reader
    script = (REPO / "scripts/windows/odysseus-host.ps1").read_text()
    assert "[string]$Profile = 'joint'" in script
    assert "PSBoundParameters.ContainsKey('DataRoot')" in script
    assert "'-Profile',$Profile" in script
    assert script.index("Assert-Configuration\n        New-Item") > script.index("    Assert-ReaderConfiguration")
    # The whole original joint path remains beneath the explicit profile branch.
    tree = ast.parse((REPO / "app.py").read_text())
    gate = next(i for i, n in enumerate(tree.body) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "RUNTIME_PROFILE" for t in n.targets))
    db_import = next(i for i, n in enumerate(tree.body) if isinstance(n, ast.ImportFrom) and n.module == "core.database")
    assert gate < db_import
    branch = next(n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == "RUNTIME_PROFILE.reader")
    assert "initialize_managers(BASE_DIR, rag_manager)" in ast.unparse(branch.orelse)
    assert "initialize_managers" not in ast.unparse(branch.body)
    assert any(isinstance(n, ast.If) and ast.unparse(n.test) == "__name__ == '__main__'" for n in tree.body)
