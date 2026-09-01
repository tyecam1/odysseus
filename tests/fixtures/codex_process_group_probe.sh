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
