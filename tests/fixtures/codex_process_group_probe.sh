#!/bin/sh
set -eu

pid_dir="${AOTERU_TEST_PID_DIR:?}"
mode="${AOTERU_TEST_MODE:-success}"
out_path=""
previous=""

for arg in "$@"; do
    if [ "$previous" = "-o" ]; then
        out_path="$arg"
        break
    fi
    previous="$arg"
done

printf '%s\n' "$$" > "$pid_dir/wrapper.pid"

if [ "$mode" = "timeout" ]; then
    sleep 30 &
    printf '%s\n' "$!" > "$pid_dir/child.pid"
    sleep 30
    exit 0
fi

if [ "$mode" = "escaped_pgid" ]; then
    # Models the topology actually observed live during the 2026-09-01
    # incident: a codex-launched MCP server child called something
    # equivalent to setpgid(0, 0), landing in its own process group
    # while remaining in the parent's session (confirmed with real
    # ps -eo pid,ppid,pgid,sid evidence during the incident). A plain
    # os.killpg(leader_pgid, SIGKILL) cannot reach a descendant like
    # this; only walking real parent-child links (or signalling the
    # whole session) does.
    python3 -c "
import os, sys, time
os.setpgid(0, 0)
sys.stdout.write(str(os.getpid()) + chr(10))
sys.stdout.flush()
time.sleep(30)
" > "$pid_dir/escaped_child.pid" &
    printf '%s\n' "$!" > "$pid_dir/child.pid"
    printf '%s\n' "$$" > "$pid_dir/wrapper.pid"
    # Give the child a moment to actually call setpgid before this
    # script (and therefore the timeout clock) proceeds, so the test
    # can rely on the escape having genuinely happened by the time it
    # inspects pgid.
    sleep 0.3
    sleep 30
    exit 0
fi

if [ "$mode" = "leader_exits_child_survives" ]; then
    # The background child inherits this script's stdout/stderr (the pipes
    # the Python parent is reading via communicate()) with no redirection,
    # so those pipes stay open as long as the child lives - even after this
    # leader process exits immediately below. Reproduces the case where the
    # wrapper/leader is gone before the timeout fires, but a descendant
    # (same process group, inherited independent of the leader) survives.
    sleep 30 &
    printf '%s\n' "$!" > "$pid_dir/child.pid"
    printf '%s\n' "$$" > "$pid_dir/wrapper.pid"
    exit 0
fi

if [ -n "$out_path" ]; then
    printf '%s' "${AOTERU_TEST_OUTPUT_TEXT:-fixture output}" > "$out_path"
fi
