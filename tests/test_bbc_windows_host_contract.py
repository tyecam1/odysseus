from pathlib import Path


HOST_SCRIPT = Path(__file__).parents[1] / "scripts" / "windows" / "odysseus-host.ps1"


def test_host_lifecycle_propagates_obsidian_repository_root() -> None:
    script = HOST_SCRIPT.read_text(encoding="utf-8")

    assert "[string]$ObsidianPhDRoot = $env:BBC_OBSIDIAN_PHD_ROOT" in script
    assert "Obsidian-PhD repository not found at $ObsidianPhDRoot" in script
    assert "$env:BBC_OBSIDIAN_PHD_ROOT = [IO.Path]::GetFullPath($ObsidianPhDRoot)" in script
    assert "@('-ObsidianPhDRoot" in script
    assert "obsidian_phd_root = $ObsidianPhDRoot" in script
