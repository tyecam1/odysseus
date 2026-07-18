import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


def _frontend_sources():
    return (
        (ROOT / "static" / "bbc" / "index.html").read_text(encoding="utf-8"),
        (ROOT / "static" / "bbc" / "ship.js").read_text(encoding="utf-8"),
        (ROOT / "static" / "bbc" / "ship.css").read_text(encoding="utf-8"),
    )


def test_ship_shell_is_live_api_driven_and_contains_no_third_party_artwork():
    html, script, css = _frontend_sources()
    assert "/api/bbc/v1/ship" in script
    assert "/api/bbc/v1/repositories" in script
    assert "dependency_ids" in script
    assert "acceptance_evidence" in script
    assert "canvas id=\"vapour-field\"" in html
    assert 'rel="icon" type="image/svg+xml" href="data:image/svg+xml' in html
    assert "Better Planets" not in html + script + css
    assert "url(http" not in css
    assert "@media (max-width: 1120px)" in css
    assert "@media (max-width: 760px)" in css


def test_colour_encodes_only_difficulty_and_state_uses_shape():
    _, script, css = _frontend_sources()
    assert "node.difficulty.band" in script
    assert "nodeShape(node" in script
    assert ".node.low" in css and ".node.medium" in css and ".node.high" in css
    assert ".node-state { fill: var(--muted);" in css
    assert "prefers-reduced-motion" in css


def test_bbc_router_is_registered_additively_in_the_application():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from routes.bbc_routes import setup_bbc_routes" in app_source
    assert "app.include_router(setup_bbc_routes())" in app_source


def test_event_telemetry_uses_the_unpaged_latest_sequence_contract():
    _, script, _ = _frontend_sources()
    assert "events.latest_sequence" in script
    assert "events.events[" not in script
    assert "Number(events.latest_sequence)" in script


def test_repository_tabs_and_work_map_have_interactive_accessibility_contracts():
    html, script, css = _frontend_sources()
    work_map_tag = html.split('<svg id="work-map"', 1)[1].split(">", 1)[0]
    assert 'role="region"' in work_map_tag
    assert 'role="img"' not in work_map_tag
    assert 'aria-describedby="work-map-help"' in work_map_tag
    assert 'role="tablist"' in html
    assert 'button.setAttribute("aria-controls", "work-map")' in script
    assert "button.tabIndex" in script
    assert all(key in script for key in ("ArrowLeft", "ArrowRight", "Home", "End"))
    assert 'role: "button"' in script
    assert 'event.key === "Enter" || event.key === " "' in script
    assert 'class: "node-hit-target"' in script
    assert "width: 44, height: 44" in script
    assert ".node-hit-target { fill: transparent;" in css
    assert "pointer-events: all" in css


def test_work_map_keeps_paused_nodes_and_expands_dense_streams_in_a_scroll_region():
    html, script, css = _frontend_sources()
    assert 'class="work-map-scroll"' in html
    assert "overflow-x: auto" in css
    assert "workMapDimensions(payload)" in script
    assert "mapMetrics.nodeGap" in script
    assert 'map.style.width = `${dimensions.width}px`' in script
    assert "payload.nodes.filter(node => node.state === \"paused\")" in script
    assert "payload.nodes.forEach(node => node.dependency_ids.forEach" in script
    assert "ACTIVE NODES" not in script


def test_node_card_exposes_source_context_and_an_honest_read_only_state():
    html, script, _ = _frontend_sources()
    for label in ("Next source action", "Available action", "Blockers", "Dependencies", "Evidence", "Source links"):
        assert f"<dt>{label}</dt>" in html
    for field in ("blocker_ids", "dependency_ids", "acceptance_evidence", "source_links"):
        assert field in script
    assert "Read-only inspection only" in html
    assert "exposes no node mutation controls" in script
    assert "<button" not in html.split('<aside id="node-card"', 1)[1].split("</aside>", 1)[0]


@pytest.mark.skipif(shutil.which("node") is None, reason="node binary not on PATH")
def test_request_generation_and_dense_layout_behavior():
    runner = textwrap.dedent(
        """
        const fs = require("node:fs");
        let source = fs.readFileSync("static/bbc/ship.js", "utf8");
        const marker = "  boot();";
        if (!source.includes(marker)) throw new Error("ship boot marker missing");
        source = source.replace(marker, `
          globalThis.__bbcTest = { state, beginSystemRequest, systemRequestIsCurrent, workMapDimensions };
        `);
        eval(source);
        const api = globalThis.__bbcTest;
        api.state.selectedSystem = "alpha";
        const first = api.beginSystemRequest("alpha");
        api.state.selectedSystem = "beta";
        const second = api.beginSystemRequest("beta");
        const dimensions = api.workMapDimensions({
          streams: [{ node_ids: Array.from({ length: 40 }, (_, index) => `node-${index}`) }],
        });
        process.stdout.write(JSON.stringify({
          firstAborted: first.controller.signal.aborted,
          firstCurrent: api.systemRequestIsCurrent(first),
          secondCurrent: api.systemRequestIsCurrent(second),
          width: dimensions.width,
        }));
        """
    )
    result = subprocess.run(
        ["node", "-e", runner],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    behavior = json.loads(result.stdout)
    assert behavior == {
        "firstAborted": True,
        "firstCurrent": False,
        "secondCurrent": True,
        "width": 3763,
    }
