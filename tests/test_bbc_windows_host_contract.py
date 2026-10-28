from pathlib import Path


HOST_SCRIPT = Path(__file__).parents[1] / "scripts" / "windows" / "odysseus-host.ps1"


def test_host_lifecycle_propagates_obsidian_repository_root() -> None:
    script = HOST_SCRIPT.read_text(encoding="utf-8")

    assert "[string]$ObsidianPhDRoot = $env:BBC_OBSIDIAN_PHD_ROOT" in script
    assert "Obsidian-PhD repository not found at $ObsidianPhDRoot" in script
    assert "$env:BBC_OBSIDIAN_PHD_ROOT = [IO.Path]::GetFullPath($ObsidianPhDRoot)" in script
    assert "@('-ObsidianPhDRoot" in script
    assert "obsidian_phd_root = $ObsidianPhDRoot" in script


def test_host_lifecycle_isolation_requires_explicit_identity_and_clears_inherited_roots() -> None:
    script = HOST_SCRIPT.read_text(encoding="utf-8")

    assert "[switch]$RequireIsolation" in script
    assert "$PSBoundParameters.ContainsKey('DataRoot')" in script
    assert "$env:ODYSSEUS_DEPLOYMENT_ISOLATION = 'required'" in script
    assert "'MISUMI_HOUSEHOLD_ROOT','MISUMI_SOURCE_ROOT','BBC_MISUMI_ROOT'" in script
    assert "'BBC_OBSIDIAN_PHD_ROOT','OBSIDIAN_PHD_ROOT'" in script
    assert "@('-RequireIsolation','-DeploymentId'" in script
