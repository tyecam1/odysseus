(() => {
  "use strict";

  const svgNS = "http://www.w3.org/2000/svg";
  const state = {
    systems: [],
    selectedSystem: null,
    sequence: 0,
    nodes: new Map(),
    requestController: null,
    requestGeneration: 0,
  };
  const mapMetrics = { left: 135, right: 40, top: 54, nodeGap: 92, laneGap: 74, minWidth: 960, minHeight: 430 };

  function svg(tag, attributes = {}, text = "") {
    const node = document.createElementNS(svgNS, tag);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (text) node.textContent = text;
    return node;
  }

  async function api(path, { signal } = {}) {
    const response = await fetch(path, { credentials: "same-origin", headers: { Accept: "application/json" }, signal });
    if (response.status === 401) {
      window.location.assign("/login");
      throw new Error("Authentication required");
    }
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || payload.error || `Request failed (${response.status})`);
    }
    return response.json();
  }

  function proceduralField() {
    const canvas = document.getElementById("vapour-field");
    const context = canvas.getContext("2d", { alpha: false });
    const draw = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas.width = Math.floor(innerWidth * ratio);
      canvas.height = Math.floor(innerHeight * ratio);
      context.scale(ratio, ratio);
      const gradient = context.createLinearGradient(0, 0, 0, innerHeight);
      gradient.addColorStop(0, "#070611");
      gradient.addColorStop(.58, "#11102a");
      gradient.addColorStop(1, "#34165f");
      context.fillStyle = gradient;
      context.fillRect(0, 0, innerWidth, innerHeight);
      let seed = 1977;
      const random = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
      for (let index = 0; index < Math.min(180, innerWidth / 5); index += 1) {
        const x = random() * innerWidth;
        const y = random() * innerHeight * .68;
        const size = random() * 1.7 + .3;
        context.fillStyle = random() > .86 ? "#ff71ce" : "rgba(221, 232, 255, .72)";
        context.fillRect(Math.round(x), Math.round(y), size, size);
      }
      context.strokeStyle = "rgba(92, 225, 230, .12)";
      context.lineWidth = 1;
      const horizon = innerHeight * .72;
      for (let y = horizon; y < innerHeight; y += Math.max(7, (y - horizon) * .16)) {
        context.beginPath(); context.moveTo(0, y); context.lineTo(innerWidth, y); context.stroke();
      }
      for (let x = -innerWidth; x < innerWidth * 2; x += 80) {
        context.beginPath(); context.moveTo(innerWidth / 2, horizon); context.lineTo(x, innerHeight); context.stroke();
      }
    };
    draw();
    window.addEventListener("resize", draw, { passive: true });
  }

  function renderShip(ship) {
    const deck = document.getElementById("deck");
    deck.replaceChildren();
    deck.append(svg("path", {
      class: "hull",
      d: "M50 1 L68 12 L91 30 L96 56 L81 77 L63 90 L37 90 L19 77 L4 56 L9 30 L32 12 Z",
    }));
    const centres = Object.fromEntries(ship.rooms.map(room => [room.id, [room.position.x + room.size.x / 2, room.position.y + room.size.y / 2]]));
    [["bridge", "commons"], ["observatory", "commons"], ["research", "commons"], ["archive", "commons"], ["engineering", "commons"], ["commons", "workshop"]].forEach(([a, b]) => {
      if (!centres[a] || !centres[b]) return;
      deck.append(svg("line", { class: "corridor", x1: centres[a][0], y1: centres[a][1], x2: centres[b][0], y2: centres[b][1] }));
    });
    ship.rooms.forEach(room => {
      const group = svg("g");
      group.append(svg("rect", {
        class: `room${room.id === ship.active_room_id ? " active" : ""}`,
        x: room.position.x, y: room.position.y,
        width: room.size.x, height: room.size.y, rx: 1,
      }));
      group.append(svg("text", { class: "room-label", x: room.position.x + 2, y: room.position.y + 6 }, room.name.toUpperCase()));
      const description = room.function.length > 27 ? `${room.function.slice(0, 27)}…` : room.function;
      group.append(svg("text", { class: "room-function", x: room.position.x + 2, y: room.position.y + 10 }, description));
      group.append(svg("title", {}, `${room.name}: ${room.function}`));
      deck.append(group);
    });
    document.getElementById("ship-meta").textContent = `${ship.deck_count} DECK / ${ship.rooms.length} ROOMS / ${ship.active_room_id.toUpperCase()}`;
  }

  function renderSystems() {
    const tabs = document.getElementById("system-tabs");
    tabs.replaceChildren();
    const reachable = state.systems.filter(system => system.reachable);
    const rovingSystem = reachable.some(system => system.id === state.selectedSystem)
      ? state.selectedSystem
      : (reachable[0] || {}).id;
    state.systems.forEach(system => {
      const button = document.createElement("button");
      button.type = "button";
      button.role = "tab";
      button.id = tabId(system.id);
      button.textContent = system.name;
      button.setAttribute("aria-selected", String(system.id === state.selectedSystem));
      button.setAttribute("aria-controls", "work-map");
      button.tabIndex = system.reachable && system.id === rovingSystem ? 0 : -1;
      button.disabled = !system.reachable;
      button.title = system.reachable ? `${system.work_node_count} canonical nodes` : (system.error || "Repository unavailable");
      button.addEventListener("click", () => {
        selectSystem(system.id);
        requestAnimationFrame(() => document.getElementById(tabId(system.id))?.focus());
      });
      button.addEventListener("keydown", event => moveTabFocus(event, system.id));
      tabs.append(button);
    });
  }

  function tabId(systemId) {
    return `system-tab-${systemId.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
  }

  function moveTabFocus(event, systemId) {
    const systems = state.systems.filter(system => system.reachable);
    const current = systems.findIndex(system => system.id === systemId);
    if (current < 0) return;
    let next = current;
    if (event.key === "ArrowRight") next = (current + 1) % systems.length;
    else if (event.key === "ArrowLeft") next = (current - 1 + systems.length) % systems.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = systems.length - 1;
    else return;
    event.preventDefault();
    const nextSystem = systems[next];
    selectSystem(nextSystem.id);
    requestAnimationFrame(() => document.getElementById(tabId(nextSystem.id))?.focus());
  }

  function nodeShape(node, x, y) {
    const stateClass = node.state;
    if (stateClass === "completed" || stateClass === "archived") {
      return svg("rect", { x: x - 7, y: y - 7, width: 14, height: 14, transform: `rotate(45 ${x} ${y})` });
    }
    if (stateClass === "blocked") return svg("polygon", { points: `${x},${y - 10} ${x + 10},${y + 8} ${x - 10},${y + 8}` });
    if (stateClass === "review") return svg("rect", { x: x - 9, y: y - 7, width: 18, height: 14, rx: 3 });
    return svg("circle", { cx: x, cy: y, r: 8 });
  }

  function workMapDimensions(payload) {
    const longestStream = Math.max(1, ...payload.streams.map(stream => stream.node_ids.length));
    return {
      width: Math.max(mapMetrics.minWidth, mapMetrics.left + (longestStream - 1) * mapMetrics.nodeGap + mapMetrics.right),
      height: Math.max(mapMetrics.minHeight, mapMetrics.top + Math.max(0, payload.streams.length - 1) * mapMetrics.laneGap + 54),
    };
  }

  function renderWorkMap(payload) {
    const map = document.getElementById("work-map");
    map.replaceChildren();
    const nodes = new Map(payload.nodes.map(node => [node.id, node]));
    state.nodes = nodes;
    const positions = new Map();
    const dimensions = workMapDimensions(payload);
    map.setAttribute("viewBox", `0 0 ${dimensions.width} ${dimensions.height}`);
    map.setAttribute("aria-labelledby", `systems-title ${tabId(payload.system.id)}`);
    map.style.width = `${dimensions.width}px`;
    map.style.height = `${dimensions.height}px`;
    payload.streams.forEach((stream, laneIndex) => {
      const y = mapMetrics.top + laneIndex * mapMetrics.laneGap;
      map.append(svg("line", { class: "lane", x1: 105, y1: y, x2: dimensions.width - 30, y2: y }));
      map.append(svg("text", { class: "lane-label", x: 18, y: y + 4 }, stream.title.toUpperCase().slice(0, 15)));
      stream.node_ids.forEach((nodeId, index) => {
        const x = mapMetrics.left + index * mapMetrics.nodeGap;
        positions.set(nodeId, { x, y });
      });
    });
    payload.nodes.forEach(node => node.dependency_ids.forEach(dependencyId => {
      const from = positions.get(dependencyId);
      const to = positions.get(node.id);
      if (from && to) map.append(svg("path", { class: "dependency", d: `M${from.x} ${from.y} C${(from.x + to.x) / 2} ${from.y}, ${(from.x + to.x) / 2} ${to.y}, ${to.x} ${to.y}` }));
    }));
    positions.forEach(({ x, y }, nodeId) => {
      const node = nodes.get(nodeId);
      if (!node) return;
      const group = svg("g", {
        class: "work-node",
        tabindex: "0",
        role: "button",
        "data-state": node.state,
        "aria-label": `${node.title}; ${node.state}; difficulty ${node.difficulty.score} of 100`,
      });
      group.append(svg("rect", { class: "node-hit-target", x: x - 22, y: y - 22, width: 44, height: 44 }));
      const shape = nodeShape(node, x, y);
      shape.setAttribute("class", `node ${node.difficulty.band}`);
      group.append(shape);
      group.append(svg("title", {}, `${node.title} — difficulty ${node.difficulty.score}/100`));
      const label = svg("text", { class: "node-state", x: x + 12, y: y + 3 }, node.state.slice(0, 3).toUpperCase());
      group.append(label);
      group.addEventListener("click", () => renderNodeCard(node));
      group.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); renderNodeCard(node); } });
      map.append(group);
    });
    const pausedCount = payload.nodes.filter(node => node.state === "paused").length;
    document.getElementById("system-status").textContent = `${payload.system.revision ? payload.system.revision.slice(0, 8) : "NO REVISION"} / ${payload.nodes.length} VISIBLE NODES / ${pausedCount} PAUSED / ${payload.streams.length} PARALLEL STREAMS / ${payload.system.ambiguity_count} AMBIGUITIES`;
  }

  function nodeReferences(ids) {
    if (!ids.length) return "None stated in the source artifact.";
    return ids.map(id => state.nodes.get(id)?.title || id).join(" · ");
  }

  function renderNodeCard(node) {
    const card = document.getElementById("node-card");
    card.querySelector("h2").textContent = node.title;
    card.querySelector(".outcome").textContent = node.outcome;
    const values = {
      state: node.state,
      difficulty: `${node.difficulty.score}/100 · ${node.difficulty.band} · model ${node.difficulty.version}`,
      owner: node.owner || "Unassigned",
      "next-action": node.next_action || "No next action stated in the source artifact.",
      "available-action": "Read-only inspection only; this interface exposes no node mutation controls.",
      blockers: nodeReferences(node.blocker_ids),
      dependencies: nodeReferences(node.dependency_ids),
      evidence: node.acceptance_evidence.length ? node.acceptance_evidence.join(" · ") : "No acceptance evidence stated.",
      "source-links": node.source_links.length ? node.source_links.join(" · ") : "No source links stated.",
    };
    Object.entries(values).forEach(([field, value]) => {
      card.querySelector(`[data-field="${field}"]`).textContent = value;
    });
  }

  function beginSystemRequest(systemId) {
    state.requestController?.abort();
    const request = {
      controller: new AbortController(),
      generation: state.requestGeneration + 1,
      systemId,
    };
    state.requestController = request.controller;
    state.requestGeneration = request.generation;
    return request;
  }

  function systemRequestIsCurrent(request) {
    return request.generation === state.requestGeneration && request.systemId === state.selectedSystem;
  }

  async function selectSystem(systemId) {
    state.selectedSystem = systemId;
    const request = beginSystemRequest(systemId);
    renderSystems();
    const map = document.getElementById("work-map");
    map.replaceChildren();
    map.setAttribute("aria-busy", "true");
    state.nodes = new Map();
    document.getElementById("system-status").textContent = "INGESTING AUTHORITATIVE WORK ITEMS…";
    try {
      const payload = await api(`/api/bbc/v1/repositories/${encodeURIComponent(systemId)}/work-nodes`, { signal: request.controller.signal });
      if (!systemRequestIsCurrent(request)) return;
      renderWorkMap(payload);
      map.setAttribute("aria-busy", "false");
    } catch (error) {
      if (error.name === "AbortError" || !systemRequestIsCurrent(request)) return;
      document.getElementById("system-status").textContent = error.message.toUpperCase();
      map.replaceChildren();
      map.setAttribute("aria-busy", "false");
    } finally {
      if (systemRequestIsCurrent(request)) state.requestController = null;
    }
  }

  async function boot() {
    proceduralField();
    try {
      const [health, ship, repositories, events] = await Promise.all([
        api("/api/bbc/v1/health"), api("/api/bbc/v1/ship"), api("/api/bbc/v1/repositories"), api("/api/bbc/v1/state/events?limit=1"),
      ]);
      renderShip(ship);
      state.systems = repositories.systems;
      const preferred = state.systems.find(system => system.id === "obsidian-phd" && system.reachable) || state.systems.find(system => system.reachable);
      state.selectedSystem = preferred ? preferred.id : null;
      renderSystems();
      const signal = document.getElementById("runtime-state");
      signal.textContent = health.status.toUpperCase();
      signal.classList.add(health.status === "healthy" ? "live" : "degraded");
      state.sequence = Number(events.latest_sequence) || 0;
      document.getElementById("event-sequence").textContent = `EVENT ${String(state.sequence).padStart(4, "0")}`;
      if (state.selectedSystem) await selectSystem(state.selectedSystem);
    } catch (error) {
      const signal = document.getElementById("runtime-state");
      signal.textContent = "OFFLINE";
      signal.classList.add("degraded");
      document.getElementById("system-status").textContent = error.message.toUpperCase();
    }
  }

  boot();
})();
